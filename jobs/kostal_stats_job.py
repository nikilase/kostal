#!/usr/bin/env python
# -*- coding: utf-8 -*-

#  webapi_kostal - Read and write access to Kostal Inverter using /dev/api access
#  Copyright (C) 2018  Kilian Knoll
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
# Please note that any incorrect or careless usage of this module as well as errors in the implementation can damage 
# your Smart Energy Meter! Therefore, the author does not provide any guarantee or warranty concerning to 
# correctness, functionality or performance and does not accept any liability for damage caused by this module, 
# examples or mentioned information. Thus, use it at your own risk!
#
#
#  Purpose:
#           Query - and Set Values for the Kostal Inverter
#
#  Based on :
# https://stackoverflow.com/questions/59053539/api-call-portation-from-java-to-python-kostal-plenticore-inverter

#
#
# Tested with:
# python 3.6.2
# Please change the following (see below):
#   IP adress of your Kostal inverter in BASE_URL
#   PASSWD that you log in to the Kostal Inverter
#


import sys
import random
import string
import base64
import json
import timeit
from datetime import datetime, time

import requests
import hashlib
import os
import hmac
from Cryptodome.Cipher import AES
from influxdb import InfluxDBClient

from config.config import KostalConf as KC
from config.config import InfluxConf as INF


def randomString(stringLength):
	letters = string.ascii_letters
	return ''.join(random.choice(letters) for i in range(stringLength))


def getPBKDF2Hash(password, bytedSalt, rounds):
	return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytedSalt, rounds)


def kostal_authorize():
	print("Connecting and signing in to Kostal")
	# Step 1: First contact using username and random nonce to receive salt and rounds for salting of password
	u = randomString(12)
	u = base64.b64encode(u.encode('utf-8')).decode('utf-8')

	step1 = {
		"username": KC.USER_TYPE,
		"nonce": u
	}
	step1 = json.dumps(step1)

	url = KC.BASE_URL + KC.AUTH_START
	headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
	response = requests.post(url, data=step1, headers=headers)
	response = json.loads(response.text)
	i = response['nonce']
	e = response['transactionId']
	o = response['rounds']
	a = response['salt']
	bitSalt = base64.b64decode(a)
	# Received the data for salting

	# Step 2: Now salt the password to proof our authenticity
	r = getPBKDF2Hash(KC.PWD, bitSalt, o)
	s = hmac.new(r, "Client Key".encode('utf-8'), hashlib.sha256).digest()
	c = hmac.new(r, "Server Key".encode('utf-8'), hashlib.sha256).digest()
	_ = hashlib.sha256(s).digest()
	d = "n=user,r=" + u + ",r=" + i + ",s=" + a + ",i=" + str(o) + ",c=biws,r=" + i
	g = hmac.new(_, d.encode('utf-8'), hashlib.sha256).digest()
	p = hmac.new(c, d.encode('utf-8'), hashlib.sha256).digest()
	f = bytes(a ^ b for (a, b) in zip(s, g))
	proof = base64.b64encode(f).decode('utf-8')

	# Authenticate using the salted password
	step2 = {
		"transactionId": e,
		"proof": proof
	}
	step2 = json.dumps(step2)

	url = KC.BASE_URL + KC.AUTH_FINISH
	headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
	response = requests.post(url, data=step2, headers=headers)
	response = json.loads(response.text)
	token = response['token']
	signature = response['signature']
	# Hopefully the authentication worked. We have now received the data for our session ID

	# Step 3: Request Session ID using some AES stuff
	y = hmac.new(_, "Session Key".encode('utf-8'), hashlib.sha256)
	y.update(d.encode('utf-8'))
	y.update(s)
	P = y.digest()
	protocol_key = P
	t = os.urandom(16)

	e2 = AES.new(protocol_key, AES.MODE_GCM, t)
	e2, authtag = e2.encrypt_and_digest(token.encode('utf-8'))

	step3 = {
		"transactionId": e,
		"iv": base64.b64encode(t).decode('utf-8'),
		"tag": base64.b64encode(authtag).decode("utf-8"),
		"payload": base64.b64encode(e2).decode('utf-8')
	}
	step3 = json.dumps(step3)

	headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
	url = KC.BASE_URL + KC.AUTH_CREATE_SESSION
	response = requests.post(url, data=step3, headers=headers)
	response = json.loads(response.text)
	global SESSION_ID
	SESSION_ID = response['sessionId']
	# We have received the Session ID and can now freely communicate with the Kostal

	# Create a new header with the new Session ID for all further requests and test if it works
	headers = {'Content-type': 'application/json', 'Accept': 'application/json',
			   'authorization': "Session " + SESSION_ID}
	url = KC.BASE_URL + KC.ME
	response = requests.get(url=url, headers=headers)
	response = json.loads(response.text)
	authOK = response['authenticated']

	if not authOK:
		print("Authorization NOT OK")
		sys.exit()
	print("Authorization OK")
	print("-----------------------")


def kostal_requests():
	"""
	Now the actual requests
	First a list of all processdata variables
	Only really needed for debugging to see if we need new data
	"""

	headers = {'Content-type': 'application/json', 'Accept': 'application/json',
			   'authorization': "Session " + SESSION_ID}
	print("Getting list of all processdata")
	url = KC.BASE_URL + "/processdata"
	response = requests.get(url=url, headers=headers)
	response = json.loads(response.text)
	all_modules = response
	print("Received the list")
	print("-----------------------")

	"""
	Get the Processdata of the PV
	"""
	print("Getting PV data")
	url = KC.BASE_URL + "/processdata/devices:local:pv1"
	response = requests.get(url=url, headers=headers)

	response = json.loads(response.text)
	pv_1 = response[0]['processdata'][1]['value']

	url = KC.BASE_URL + "/processdata/devices:local:pv2"
	response = requests.get(url=url, headers=headers)

	response = json.loads(response.text)
	pv_2 = response[0]['processdata'][1]['value']

	"""
	Get the Processdata of the battery
	"""

	print("Getting Battery data")
	url = KC.BASE_URL + "/processdata/devices:local:battery"
	response = requests.get(url=url, headers=headers)

	response = json.loads(response.text)

	soc = response[0]['processdata'][8]['value']
	bat_power = response[0]['processdata'][7]['value']

	"""
	Get the Processdata of the device usage
	"""

	print("Getting rest of the kostal data for consumption")
	url = KC.BASE_URL + "/processdata/devices:local"
	response = requests.get(url=url, headers=headers)
	response = json.loads(response.text)
	print("Received all needed data")
	print("-----------------------")

	"""
	Get the Processdata of the device usage
	"""

	print("Getting power meter data for usage")
	url = KC.BASE_URL + "/processdata/scb:statistic:EnergyFlow"
	response_sbc = requests.get(url=url, headers=headers)
	response_sbc = json.loads(response_sbc.text)
	data = response_sbc[0]['processdata']
	print("Received all needed data")
	print("-----------------------")

	autarky = data[0]['value']

	#
	energy_charge_grid = data[8]['value']
	energy_charge_inv = data[12]['value']
	energy_charge_pv = data[16]['value']
	energy_discharge = data[20]['value']
	energy_home_discharge_grid = data[24]['value']

	energy_home = data[28]['value']
	energy_home_bat = data[32]['value']
	energy_home_grid = data[36]['value']
	energy_home_pv = data[41]['value']

	# Total PV generation shall be calculated by addition of all (here just 2, could also be three or one) phases
	energy_pv1 = data[45]['value']
	energy_pv2 = data[49]['value']
	energy_total = energy_pv1 + energy_pv2

	rough_sold = energy_total - energy_home_pv - energy_charge_pv

	# Percent of home usage of PV? Could be as wrong as the own_yield field?
	own_consumption = data[57]['value']

	# Looks like it just calculates pv usage + battery usage.
	# May be wrong as battery usage of yesterdays battery (energy harvested yesterday) will also be included here
	own_yield = data[61]['value']

	solar_charge_till_now = data[45]['value'] + data[49]['value']
	home_consumption_till_now = data[28]['value']
	home_from_grid = data[36]['value']
	home_to_grid = home_consumption_till_now - home_from_grid

	"""
	Now we need to go through all data and send it to the database
	"""

	bat2grid = response[0]['processdata'][0]['value']
	dc_p = response[0]['processdata'][1]['value']
	grid2bat = response[0]['processdata'][2]['value']
	grid_p = response[0]['processdata'][11]['value']
	home_bat = response[0]['processdata'][14]['value']
	home_grid = response[0]['processdata'][15]['value']
	home_own = response[0]['processdata'][16]['value']
	home_pv = response[0]['processdata'][17]['value']
	home_p = response[0]['processdata'][18]['value']
	pv2bat = response[0]['processdata'][23]['value']

	pv_usage = home_pv + pv2bat
	bat_usage = bat2grid + home_bat
	bat_charge = grid2bat + pv2bat
	grid_usage1 = home_grid + grid2bat
	grid_usage = grid_p
	dif = grid_usage1 - grid_usage
	home_usage = home_own

	bat_actual = bat_charge - bat_usage
	pv_gen = pv_1 + pv_2

	print(f"home usage: {home_usage}W")
	print(f"battery usage: {bat_usage}W")
	print(f"battery charging: {bat_charge}W")
	print(f"solar generation: {pv_usage}W")
	print(f"grid usage: {grid_usage}W")
	print(f"battery soc: {soc}%")

	print(f"PV till now: {solar_charge_till_now}Wh")
	print(f"Usage till now: {home_consumption_till_now}Wh")

	client = InfluxDBClient(host=INF.HOST, port=INF.PORT, username=INF.USER, password=INF.PASSWORD, ssl=INF.SSL,
							verify_ssl=INF.VERIFY_SSL, database=INF.DB)

	json_body = [
		{
			"measurement": INF.MSRMT_POWER,
			"fields": {
				"home": home_p,
				"pv": pv_gen,
				"battery": bat_power,
				"grid": grid_p,
				"soc": soc,
				"home_day": home_consumption_till_now,
				"pv_day": solar_charge_till_now
			}
		}
	]
	#KC.PP.pprint(json_body)

	client.write_points(json_body)

	# Initializer for just after midnight
	# I think this was needed when the grid usage was zero over the night as the battery was still full
	# This lead to the aggregates being wrong
	if datetime.now().time() <= time(hour=0, minute=0, second=20):
		print("Yeah")
		json_body = [
			{
				"measurement": INF.MSRMT_POWER,
				"fields": {
					"grid": 0.0,
				}
			}
		]

		client.write_points(json_body)

	client.close()


def main():
	print(f"start {datetime.now().time()}")
	duration = timeit.timeit(lambda: kostal_authorize(), number=1)
	print(f"Auth Time {duration}s.")
	#kostal_authorize()

	#kostal_requests()
	duration = timeit.timeit(lambda: kostal_requests(), number=1)
	print(f"Request Time {duration}s.")
	print(f"end {datetime.now().time()}")


if __name__ == "__main__":
	main()
