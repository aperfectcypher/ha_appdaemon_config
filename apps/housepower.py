import appdaemon.plugins.hass.hassapi as hass

import requests

import json

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

### Get full-house power consumption from Peblar EV charger CT clamps

class HousePower(hass.Hass):

  sessionCookie = ''

  def initialize(self):
    self.auth()
    self.run_every(self.read_power, "now", 10) # update every 10 sec

  def auth(self):
    ip = self.args["peblar_ip"]
    password = self.args["peblar_password"]
    url = f"http://{ip}/system/3"
    
    # setup the browser
    service = Service(executable_path=r'/usr/bin/chromedriver')
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(service=service, options=options)

    driver.get(url)

    # Login
    wait = WebDriverWait(driver, 5)
    element = wait.until(EC.presence_of_element_located((By.ID, 'password')))
    pass_field = driver.find_element(By.ID, "password")
    pass_field.send_keys(password)

    button_xpath = "//button[contains(text(), 'Sign in')]"
    button = driver.find_element(By.XPATH, button_xpath)
    button.click()

    # Wait to find at least on current measurement (ending in ' A')
    table_xpath = "//div[contains(text(), ' A')]"
    element = wait.until(EC.presence_of_element_located((By.XPATH, table_xpath)))

    all_cookies=driver.get_cookies()
    cookies_dict = {}
    for cookie in all_cookies:
        cookies_dict[cookie['name']] = cookie['value']

    self.sessionCookie = cookies_dict['sessionid']
    print("New session cookie: ", self.sessionCookie)

    driver.close()


  def read_power(self, kwargs):
    headers = {
    "Cookie": "sessionid="+self.sessionCookie,
    }
    ip = self.args["peblar_ip"]
    diag_url = f"http://{ip}/api/v1/system/diagnostics/snapshot?Type=LiveDiagnostics"
    r = requests.get(diag_url, headers=headers)
    if r.status_code == 401: #unauthorized, re-auth
      self.auth()

    if r.status_code != 200:
      print("Request returned unexpected error code: ", r.status_code)
      print(r.text)
      return

    data = json.loads(r.text)
    
    ### Convert to Watts
    phases_amps_str = []
    phases_amps = []
    phases_power = []

    phases_volts_str = []
    phases_volts = []

    for i in range(3):
        phases_amps_str.append(str(data['Signals'][0]['Value'][i]))
        phases_amps.append(float(phases_amps_str[i]))
        phases_volts_str.append(str(data['Signals'][2]['Value'][i]))
        phases_volts.append(float(phases_volts_str[i]))
        phases_power.append(phases_amps[i]*phases_volts[i])

    # charge limit (in amps) from dynamic load balancing 
    charge_limit = float(str(data['Signals'][3]['Value'][0]))
    
    # Write values to HA entities
    self.set_value("input_number.house_power_phase_1",phases_power[0])
    self.set_value("input_number.house_power_phase_2",phases_power[1])
    self.set_value("input_number.house_power_phase_3",phases_power[2])
    self.set_value("input_number.ev_charger_limit", charge_limit)
    
