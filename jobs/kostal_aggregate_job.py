import timeit
from datetime import datetime

from influxdb import InfluxDBClient
from influxdb.resultset import ResultSet
from config.config import InfluxConf as INF
from config.config import KostalConf as KC

class DailyEnergy:
	time: str
	used = 0
	sold = 0
	saved = 0
	power: dict

	def __init__(self, time=""):
		self.time = time
		self.power = dict()
		self.power['daily_used'] = 0
		self.power['daily_sold'] = 0
		self.power['daily_saved'] = 0

	def print(self):
		print(f"used: {self.used} sold: {self.sold} saved: {self.saved}")

	def to_string(self):
		return f"used: {self.used} sold: {self.sold} saved: {self.saved}"


power_type = ["daily_used", "daily_sold", "daily_saved"]


def sort_to_daily(day_dict: dict, power_list: list, power: int):
	elem_id = power_type[power]

	for elem in power_list:
		time = elem["time"]
		used = elem[elem_id]
		obj: DailyEnergy
		if time in day_dict:
			obj = day_dict[time]
		else:
			obj = DailyEnergy(time)
		obj.power[elem_id] = used
		day_dict[time] = obj
	return day_dict


def get_cumulative(startdate: str, enddate: str):
	client = InfluxDBClient(host=INF.HOST, port=INF.PORT, username=INF.USER, password=INF.PASSWORD, ssl=INF.SSL,
								verify_ssl=INF.VERIFY_SSL, database=INF.DB)

	query_used = f"""SELECT cumulative_sum(integral(grid)) / 3600 / 1000 * {KC.BUY_PRICE} AS daily_used 
					FROM power 
					WHERE grid >= 0 AND time > '{startdate}'
					GROUP BY time(1d) fill(0) tz('{INF.TZ}')"""

	query_sold = f"""SELECT cumulative_sum(integral(grid)) / 3600 / 1000 * -{KC.SELL_PRICE} AS daily_sold 
					FROM power 
					WHERE grid <= 0 AND time > '{startdate}'
					GROUP BY time(1d) fill(0) tz('{INF.TZ}')"""

	query_save = f"""SELECT (cumulative_sum(integral(H)) - cumulative_sum(integral(G))) / 3600 /1000 * {KC.BUY_PRICE} 
					AS daily_saved 
					FROM(
						SELECT grid AS G FROM power WHERE grid >= 0 AND time > '{startdate}'
					), (
						SELECT home AS H FROM power WHERE time > '{startdate}'
					)
					GROUP BY time(1d) fill(0) tz('{INF.TZ}')"""

	result_used: ResultSet = client.query(query_used)
	result_sold: ResultSet = client.query(query_sold)
	result_save: ResultSet = client.query(query_save)

	list_used: list = list(result_used.get_points())
	list_sold: list = list(result_sold.get_points())
	list_save: list = list(result_save.get_points())

	#print(list_used[-1])#507.62596071233736
	#print(list_sold[-1])#-431.0434612127118
	#print(list_save[-1])#1309.9273575303025

	#print(len(list_used))
	#print(len(list_sold))
	#print(len(list_save))

	day_dict = {}

	day_dict = sort_to_daily(day_dict, list_used, 0)
	day_dict = sort_to_daily(day_dict, list_sold, 1)
	day_dict = sort_to_daily(day_dict, list_save, 2)

	points = []
	for day, obj in day_dict.items():
		#print(day, "->", obj.power, obj.to_string())
		power = obj.power
		body = {
			"measurement": "daily_power",
			"fields": {
				"daily_used": float(power["daily_used"]),
				"daily_sold": float(power["daily_sold"]),
				"daily_saved": float(power["daily_saved"])
			},
			"time": day
		}
		points.append(body)
		#print(body)

	client.write_points(points)
	client.close()

	print(f"Written {len(points)} entries from {startdate} till {enddate}.")


def main():
	date = datetime.today()
	year = date.year

	enddate = date.strftime("%Y-%m-%d")
	query_date = f"{year}-01-01 00:00:00"
	duration = timeit.timeit(lambda: get_cumulative(startdate=query_date, enddate=enddate), number=1)
	print(f"Execution time {duration}s.")


if __name__ == "__main__":
	main()
