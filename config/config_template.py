import pprint
from dataclasses import dataclass


@dataclass
class InfluxConf:
	HOST: str = "localhost"
	PORT: str = "8086"
	DB: str = "db"
	MSRMT: str = "measurement"
	RET: str = "autogen"
	USER: str = "user"
	PASSWORD: str = "password"
	TZ: str = "Europe/Berlin"
	PREC: str = "s"
	CONS: str = "one"
	SSL: bool = False
	VERIFY_SSL: bool = False


@dataclass
class KostalConf:
	USER_TYPE: str = "user"
	PWD: str = "password"
	BASE_URL: str = "http://0.0.0.0/api/v1"
	# Price to buy or sell one kWh from the grid
	BUY_PRICE: float = 0.5
	SELL_PRICE: float = 0.05

	# Constants
	SESSION_ID = ""
	AUTH_START = "/auth/start"
	AUTH_FINISH = "/auth/finish"
	AUTH_CREATE_SESSION = "/auth/create_session"
	ME = "/auth/me"
	PP = pprint.PrettyPrinter(indent=4)
