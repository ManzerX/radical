# identifier per post: css-g5y9jx r-18u37iz r-uaa2di

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
import time

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

def post_scraper():
    pass



if __name__ == '__main__':
    url = "https://bsky.app/search?q=since%3A2024-01-01+until%3A2024-12-31"
    options = Options
    driver = webdriver.FireFox(options=options)
