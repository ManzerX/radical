# identifier per post: css-g5y9jx r-18u37iz r-uaa2di

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

import time
import os

from dotenv import load_dotenv

def login(driver,url):
    driver.get(url)
    time.sleep(2.0)
    driver.find_element(By.CSS_SELECTOR,'button[aria-label=Aanmelden] div[class=css-146c3p1]').click() #PAS OP, NEDERLANDS!!

    load_dotenv()

    bs_user = os.getenv('USER')
    bs_pass = os.getenv('PASS')

    user_field = driver.find_element(By.CSS_SELECTOR,'input[data-testid="loginUsernameInput"]')
    pass_field = driver.find_element(By.CSS_SELECTOR,'input[data-testid="loginPasswordInput"]')

    user_field.send_keys(bs_user)
    pass_field.send_keys(bs_pass)

    time.sleep(3.0)

    driver.find_element(By.CSS_SELECTOR,'button[data-testid=loginNextButton]').click()


def scroll_to_bottom(driver):
    SCROLL_PAUSE_TIME = 1.0

    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);")

        time.sleep(SCROLL_PAUSE_TIME)

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def post_scraper(url, driver):
    zoektermen = ['test','test2']
    data = {
        "date":[],
        "message":[],
        "likes":[],
        "replies":[],
        "media":[]
    }
    for term in zoektermen:
        driver.get(url + term)
        scroll_to_bottom(driver)
        posts = driver.find_elements(By.CSS_SELECTOR,"div[class=css-g5y9jx r-18u37iz r-uaa2di]")

        for post in posts:
            print(post)


if __name__ == '__main__':
    url = "https://bsky.app/search?q=since%3A2025-01-20+until%3A2026-01-20+"
    options = Options()
    options.add_argument('--disable-blink-features=AutomationControlled')
    driver = webdriver.Firefox(options=options)
    login(driver,url)
    # posts = post_scraper(url, driver)
    # driver.quit()
