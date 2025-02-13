from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Configuração do ChromeDriver
chrome_driver_path = "/caminho/para/o/chromedriver"
service = Service(executable_path=chrome_driver_path)
options = Options()
options.add_argument("--disable-blink-features=AutomationControlled")
driver = webdriver.Chrome(service=service, options=options)

def obter_link_pauta(data):
    try:
        # Navegar para a página da agenda da Câmara dos Deputados
        url_agenda = f"https://www.camara.leg.br/agenda?dataInicial={data}&dataFinal={data}&categorias=Plen%C3%A1rio"
        driver.get(url_agenda)
        time.sleep(2)  # Aguardar o carregamento da página

        # Localizar o link da sessão plenária
        link_sessao = driver.find_element(By.XPATH, "//a[contains(text(), 'Sessão Deliberativa')]")
        link_sessao.click()
        time.sleep(2)  # Aguardar o carregamento da página

        # Localizar o link "Documentos da Sessão"
        link_documentos = driver.find_element(By.XPATH, "//a[contains(text(), 'Documentos da Sessão')]")
        link_documentos.click()
        time.sleep(2)  # Aguardar o carregamento do pop-up

        # Localizar o link "Pauta" no pop-up
        link_pauta = driver.find_element(By.XPATH, "//a[contains(text(), 'Pauta')]")
        url_pauta = link_pauta.get_attribute('href')

        return url_pauta

    except Exception as e:
        print(f"Erro ao obter o link da pauta: {e}")
        return None

    finally:
        driver.quit()

# Exemplo de uso
data_desejada = "13/02/2025"
link_pauta = obter_link_pauta(data_desejada)
if link_pauta:
    print(f"O link direto para a Pauta do dia {data_desejada} é: {link_pauta}")
else:
    print(f"Não foi possível encontrar a Pauta para a data {data_desejada}.")
