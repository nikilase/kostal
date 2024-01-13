# Kostal API Requester App 
Little app to get current power data from kostal solar inverter and send it to an influxdb v1 time series database.

Also has the feature of calculating the daily amount of electricity sold to the grid or bought from the grid, 
with the option to set how much money one kWh costs to buy or sell.

## Installation
Make sure you have an influxdb (version 1) installed and configured your config/config_template.py saving the modified
template as config/config.py

## Usage
By default, this app runs the data requester every 10 seconds and the aggregation every 5 minutes.
You can change this in the main.py file with the schedule.every() functions

App was tested on Python 3.11