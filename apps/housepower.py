import appdaemon.plugins.hass.hassapi as hass

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

### Get full-house power consumption from Peblar EV charger CT clamps

class HousePower(hass.Hass):

  def initialize(self):
    self.run_every(self.read_amps, "now", 20) # update every 20 sec

  def read_amps(self, kwargs):  
    # passing secrets: https://appdaemon.readthedocs.io/en/latest/APPGUIDE.html#secrets
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

    # get all current measurements
    current_measurements = driver.find_elements(By.XPATH, "//div[contains(text(), ' A')]")

    # Convert to Watts
    phases_amps_str = []
    phases_amps = []
    phases_power = []

    for i in range(3):
        phases_amps_str.append(str(current_measurements[i].text))
        phases_amps.append(float(phases_amps_str[i][:4]))
        phases_power.append(phases_amps[i]*230)
    
    # Write values to HA entities
    self.set_value("input_number.house_power_phase_1",phases_power[0])
    self.set_value("input_number.house_power_phase_2",phases_power[1])
    self.set_value("input_number.house_power_phase_3",phases_power[2])

    driver.close()
