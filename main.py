import sys
import time

import schedule
from apscheduler.schedulers.blocking import BlockingScheduler

from jobs.kostal_aggregate_job import main as a_m
from jobs.kostal_stats_job import main as k_m


def main():
    schedule.every(10).seconds.do(k_m)
    schedule.every(5).minutes.do(a_m)

    try:
        while True:
            schedule.run_pending()
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Shutting down from Keyboard Interrupt!")
        sys.exit()


def main_apscheduler():
    scheduler = BlockingScheduler()
    try:

        scheduler.add_job(k_m, "cron", second="0/10")
        scheduler.add_job(a_m, "cron", minute="0/5")
        scheduler.start()
    except KeyboardInterrupt:
        print("Shutting down from Keyboard Interrupt!")
        scheduler.shutdown(wait=False)
        sys.exit()


if __name__ == "__main__":
    main_apscheduler()
