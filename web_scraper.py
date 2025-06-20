import asyncio
import aiohttp
import re
import json
from bs4 import BeautifulSoup
from dh_headers import headers, urls
from datetime import date

# List of meals and macronutrients
MEALS = ["Breakfast", "Lunch", "Dinner"]
MACROS = ["Protein", "Total Fat", "Tot. Carb"]

# Regex expression for getting calories
regex_cals = r"(\d+)"

# Regex expression for getting the macro amounts
regex_macros = r"(\d+.\d?.*)"

# Getting today's date for url_add_on

# today = date.today() # Commented out for testing purposes.
today = date(2025, 5, 25)

date_url = today.strftime("%m %d %y").split(" ")
url_add_on = "&WeeksMenus=UCSC+-+This+Week%27s+Menus&dtdate={}%2f{}%2f{}".format(
    date_url[0], date_url[1], date_url[2]
)

# Function to asynchronously get a singular food item's data
async def fetch_food_data(session, url, headers):
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            fi_soup = BeautifulSoup(await response.text(), "lxml")

            # Getting the macro nutrients
            macro_data = {}
            td_data = fi_soup.find_all("td")
            for td in td_data:
                font_tags = td.find_all("font")
                if len(font_tags) == 2:
                    for m in MACROS:
                        if m in str(font_tags[0]):
                            amount = (
                                re.search(regex_macros, str(font_tags[1])).group(0)
                            )[3:-8]
                            macro_data[m] = amount

            # Getting the name of the food item
            food_name = str(fi_soup.find("div", class_="labelrecipe"))[25:-6]

            # Getting the calories
            b_tags = fi_soup.find_all("b")
            b_tags = [str(b) for b in b_tags]

            calories = "".join([s for s in b_tags if "Calories" in s])
            calories = re.search(regex_cals, calories).group(0)
            if int(calories) == 0:
                return None

            # Getting the allergens
            allergens = fi_soup.find_all("img")
            allergen_list = [str(allergen).split('"')[1] for allergen in allergens]

            return {
                "name": food_name,
                "calories": calories,
                "allergens": allergen_list,
                "macros": macro_data,
            }
        else:
            print(f"Failed to fetch the page. Status code: {response.status}")
            return None


# Function to asynchronously get the menu data
async def fetch_and_process_menu_data(
    session, dh, meal, urls, url_add_on, headers, menu_json
):
    menu_json[dh][meal] = []
    dh_meal_url = urls[dh] + url_add_on + f"&mealName={meal}"

    async with session.get(dh_meal_url, headers=headers[dh]) as long_menu:
        if long_menu.status == 200:
            lm_soup = BeautifulSoup(await long_menu.text(), "lxml")
            all_day_tag = lm_soup.find(
                "div", class_="longmenucolmenucat", string="-- All Day --"
            )
            if all_day_tag:
                href_tags = [a.get("href") for a in all_day_tag.find_all_previous("a")]
            else:
                href_tags = [a.get("href") for a in lm_soup.find_all("a")]

            tasks = []
            for href in href_tags:
                if href and "label.aspx" in href:
                    food_item_url = "https://nutrition.sa.ucsc.edu/" + href
                    tasks.append(fetch_food_data(session, food_item_url, headers[dh]))

            food_items = await asyncio.gather(*tasks)
            menu_json[dh][meal].extend(item for item in food_items if item)
        else:
            print(f"Failed to fetch the page. Status code: {long_menu.status}")


async def main():
    menu_json = {}

    async with aiohttp.ClientSession() as session:
        tasks = []
        for dh in headers.keys():
            menu_json[dh] = {}
            for meal in MEALS:
                tasks.append(
                    fetch_and_process_menu_data(
                        session, dh, meal, urls, url_add_on, headers, menu_json
                    )
                )
        await asyncio.gather(*tasks)

    with open("food.json", "w") as outfile:
        json.dump(menu_json, outfile)


if __name__ == "__main__":
    asyncio.run(main())


def testFcn():
    asyncio.run(main())
