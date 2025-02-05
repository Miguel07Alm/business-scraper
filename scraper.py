from urllib.parse import unquote, urlparse, parse_qs
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.chrome.webdriver import WebDriver
import pandas as pd
import time
from datetime import datetime
from typing import Dict, List, Optional, TypedDict, Union
import re
from pathlib import Path
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LocationConfig(TypedDict):
    ciudad: str
    pais: str
    query: str
    num_scrolls: Union[int, str]

class BusinessInfo(TypedDict):
    nombre: str
    fecha_registro: str
    tipo_negocio: str
    direccion: str
    telefono: str
    web: str
    url_gmaps: str
    valoracion: str
    num_resenas: int
    ciudad: str
    pais: str

def initialize_chrome_driver() -> WebDriver:
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--start-maximized')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-notifications')
    options.page_load_strategy = 'eager'
    
    driver = webdriver.Chrome(options=options)
    driver.set_window_size(1920, 1080)
    driver.set_window_position(0, 0)
    driver.set_page_load_timeout(20)
    driver.implicitly_wait(5)
    
    return driver

def validar_telefono(numero: str) -> bool:
    patron = r"^\d{3} \d{2} \d{2} \d{2}$|^\d{9}$"
    return bool(re.match(patron, numero))

def limpiar_url(texto: str) -> Optional[str]:
    dominios_validos = ['.com', '.es', '.shop', '.io', '.eu', '.net']
    palabras_invalidas = ['reseña', 'review', '(', ')', 'mediterránea']
    
    if any(x in texto.lower() for x in palabras_invalidas):
        return None
    
    texto = texto.strip().lower()
    if '.' in texto:
        try:
            if '//' not in texto:
                texto = texto.split('/')[-1]
            
            if any(texto.find(x) != -1 for x in dominios_validos):
                if not texto.startswith('http'):
                    texto = f"https://{texto}"
                return texto
        except Exception:
            return None
    return None

def wait_for_element(driver: WebDriver, by: By, value: str, timeout: int = 5) -> Optional[WebElement]:
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
    except:
        return None

def extract_business_info(element: WebElement, driver: WebDriver, location_config: LocationConfig) -> Optional[BusinessInfo]:
    try:
        a_element = element.find_element(By.CSS_SELECTOR, "a")
        if not a_element or not a_element.get_attribute("href"):
            return None

        name = unquote(a_element.get_attribute("href").split("place/")[1].split("/")[0].replace("+", " "))
        a_element.click()
        time.sleep(1)

        scrollable_div = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, f"//div[.//h1[text()='{name}'] and contains(@style, 'width: 408px')]"))
        )

        info: BusinessInfo = {
            'nombre': name,
            'fecha_registro': datetime.now().strftime("%Y-%m-%d"),
            'tipo_negocio': '',
            'direccion': '',
            'telefono': '',
            'web': '',
            'url_gmaps': driver.current_url,
            'valoracion': '',
            'num_resenas': 0,
            'ciudad': location_config['ciudad'],
            'pais': location_config['pais']
        }

        details_elements = scrollable_div.find_elements(By.CSS_SELECTOR, "div.fontBodyMedium")
        
        # Primera pasada para extracción básica
        for detail in details_elements:
            text = detail.text.strip()
            if not text:
                continue
                
            # Extraer tipo de negocio (suele estar en la descripción)
            if 'bar' in text.lower() or 'restaurante' in text.lower() or 'pub' in text.lower():
                info['tipo_negocio'] = text.split('\n')[0]
            elif validar_telefono(text):
                info['telefono'] = text
            elif '.' in text.lower():
                website = limpiar_url(text)
                if website:
                    info['web'] = website
            elif ',' in text and any(char.isdigit() for char in text):
                info['direccion'] = text

        # Extracción de valoración y reseñas
        if rating := wait_for_element(driver, By.CSS_SELECTOR, "div.fontDisplayLarge"):
            info['valoracion'] = rating.text

        if reviews := wait_for_element(element, By.XPATH, "//span[contains(@aria-label, 'reseña')]"):
            review_text = reviews.text.strip('()')
            if review_text.isdigit():
                info['num_resenas'] = int(review_text)

        return info

    except Exception as e:
        logger.error(f"Error extracting business info: {e}")
        return None

def get_restaurant_id(url: str) -> str:
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if '!1s' in url:
            place_id = url.split('!1s')[1].split('!')[0]
        else:
            place_id = parsed.path.split('/')[-1]
        return place_id
    except Exception as e:
        logger.warning(f"Could not extract place ID from URL: {e}")
        return url

def reject_cookies(driver: WebDriver) -> None:
    try:
        logger.info("Attempting to reject cookies...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        
        reject_button_selectors = [
            "//button[contains(., 'Rechazar todo')]",
            "//button[contains(., 'Reject all')]",
            "//button[contains(@aria-label, 'Rechazar')]",
            "button[aria-label*='Reject']"
        ]
        
        for selector in reject_button_selectors:
            try:
                if selector.startswith("//"):
                    button = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    button = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                button.click()
                logger.info("Successfully rejected cookies")
                return
            except:
                continue
        
        logger.warning("Could not find reject cookies button")
    except Exception as e:
        logger.warning(f"Error rejecting cookies: {e}")

def clean_restaurant_name(name: str) -> str:
    cleaned = re.sub(r'[^\w\s]', '', name.lower())
    common_words = ['restaurante', 'resto', 'bar', 'cafeteria', 'cafe']
    for word in common_words:
        cleaned = cleaned.replace(word, '')
    return ' '.join(cleaned.split())

def save_to_excel(df: pd.DataFrame, ciudad: str) -> None:
    excel_file = 'negocios_total.xlsx'
    logger.info(f"Saving/Updating data in {excel_file}...")
    
    try:
        if os.path.exists(excel_file):
            existing_df = pd.read_excel(excel_file)
            updated_df = pd.concat([existing_df, df], ignore_index=True)
            updated_df['nombre_normalizado'] = updated_df['nombre'].apply(clean_restaurant_name)
            updated_df = updated_df.drop_duplicates(subset=['nombre_normalizado', 'ciudad'], keep='last')
            updated_df = updated_df.drop(columns=['nombre_normalizado'])
        else:
            updated_df = df
            
        updated_df.to_excel(excel_file, index=False)
        logger.info(f"Successfully updated {excel_file} - Total entries: {len(updated_df)}")
        
        city_file = f"negocios_{ciudad.lower()}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        df.to_excel(city_file, index=False)
        logger.info(f"Created city-specific backup: {city_file}")
        
    except Exception as e:
        logger.error(f"Error saving to Excel: {e}")
        backup_file = f"negocios_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df.to_excel(backup_file, index=False)
        logger.info(f"Created backup file: {backup_file}")

def main() -> None:
    query = input("Tipo de búsqueda: ") or "restaurantes"
    ciudad = input("Ciudad: ") or "Almeria"
    pais = input("País: ") or "España"
    num_scrolls = input("Número de desplazamientos: ") or "5"
    
    config = LocationConfig(
        ciudad=ciudad,
        pais=pais,
        query=query,
        num_scrolls=num_scrolls
    )
    
    driver = initialize_chrome_driver()
    datos_restaurantes = []
    nombres_procesados = {}
    
    try:
        logger.info("Navigating to Google Maps...")
        driver.get("https://www.google.com/maps")
        time.sleep(1)
        
        reject_cookies(driver)
        
        search_query = f"{query} en {ciudad}, {pais}"
        logger.info(f"Searching for: {search_query}")
        
        search_box = wait_for_element(driver, By.ID, "searchboxinput", timeout=10)
        if not search_box:
            raise Exception("Could not find search box")
        search_box.send_keys(search_query)
        search_box.send_keys(Keys.RETURN)
        time.sleep(2)
        
        logger.info("Waiting for results container...")
        scrollable_div = wait_for_element(driver, By.CSS_SELECTOR, "div.ecceSd")
        if not scrollable_div:
            raise Exception("Could not find results container")
        
        logger.info("Beginning restaurant data collection...")
        seen_restaurants = {}
        
        for scroll_count in range(int(num_scrolls)):
            try:
                logger.info(f"Scroll iteration {scroll_count + 1}/{num_scrolls}")
                driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable_div)
                time.sleep(1)
                
                restaurants = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK")
                logger.info(f"Found {len(restaurants)} restaurants in current view")
                
                for idx, restaurant in enumerate(restaurants):
                    logger.info(f"Processing restaurant {idx}/{len(restaurants)}")
                    try:
                        restaurant.screenshot(f"negocio_{idx}.png")
                        info = extract_business_info(restaurant, driver, config)
                        if info:
                            normalized_name = clean_restaurant_name(info['nombre'])
                            
                            if normalized_name in seen_restaurants:
                                logger.info(f"Found duplicate restaurant: {info['nombre']} (normalized: {normalized_name})")
                                existing_info = seen_restaurants[normalized_name]
                                if (len([v for v in info.values() if v]) > 
                                    len([v for v in existing_info.values() if v])):
                                    seen_restaurants[normalized_name] = info
                                    logger.info(f"Updated with more complete information")
                                continue
                                
                            seen_restaurants[normalized_name] = info
                            logger.info(f"Added new restaurant: {info['nombre']} (normalized: {normalized_name})")
                            
                    except Exception as e:
                        logger.error(f"Error processing restaurant: {e}", exc_info=True)
                    
                driver.back()
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error during scroll iteration: {e}", exc_info=True)
        
        datos_restaurantes = list(seen_restaurants.values())
        logger.info(f"Total unique restaurants collected: {len(datos_restaurantes)}")
        
        df = pd.DataFrame(datos_restaurantes)
        
        save_to_excel(df, ciudad)
        
        csv_filename = f"restaurantes_{ciudad.lower()}_{datetime.now().strftime('%Y%m%d')}.csv"
        df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        logger.info(f"CSV backup created: {csv_filename}")
        
        logger.info("Data export completed successfully")
        
    except Exception as e:
        logger.error("Fatal error during scraping process", exc_info=True)
    finally:
        logger.info("Closing Chrome driver...")
        driver.quit()
        logger.info("Scraping process completed")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical("Application failed", exc_info=True)
