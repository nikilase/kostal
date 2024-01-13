import sys
import threading

import schedule
import time

from jobs.kostal_stats_job import main as k_m
from jobs.kostal_aggregate_job import main as a_m


def main():
	schedule.every(10).seconds.do(k_m)
	schedule.every(30).seconds.do(a_m)

	try:
		while True:
			schedule.run_pending()
			time.sleep(0.5)
	except KeyboardInterrupt:
		print("Shutting down from Keyboard Interrupt!")
		sys.exit()


if __name__ == "__main__":
	main()
