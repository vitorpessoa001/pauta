import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# 🛠 Configuração do WebDriver (Baixa o ChromeDriver automaticamente)
def iniciar_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Executa sem interface gráfica
    chrome_options.add_argument("--no-sandbox")  # Necessário para rodar no Streamlit Cloud
    chrome_options.add_argument("--disable-dev-shm-usage")  # Evita problemas de memória

    service = Service(ChromeDriverManager().install())  # Baixa o WebDriver automaticamente
    return webdriver.Chrome(service=service, options=chrome_options)

# 📌 Função para buscar a Sessão Deliberativa do dia
def buscar_sessao_deliberativa(data_final_formatada):
    driver = iniciar_driver()
    url_agenda = f"https://www.camara.leg.br/agenda?dataInicial={data_final_formatada}&dataFinal={data_final_formatada}&categorias=Plen%C3%A1rio"
    driver.get(url_agenda)
    time.sleep(3)

    try:
        sessoes_elementos = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, '//*[@id="busca-agenda"]/section[3]/div[2]/ul/li'))
        )

        for sessao in sessoes_elementos:
            titulo_sessao = sessao.text
            if "Sessão Deliberativa" in titulo_sessao:
                link_sessao = sessao.find_element(By.XPATH, './/div/div[2]/a').get_attribute("href")
                driver.quit()  # Fecha o WebDriver corretamente
                return link_sessao

        driver.quit()
        return None
    except:
        driver.quit()
        return None

# 🎨 Estilização da Página
st.set_page_config(page_title="Consulta de Pautas da Câmara", layout="wide")
st.title("🗳️ Consulta de Pautas da Câmara dos Deputados 🇧🇷")

# 📅 Seleção de Data pelo Usuário
data_escolhida = st.date_input("📅 Escolha uma data")

# 📌 Botão para buscar a pauta
if st.button("🔍 Buscar Pauta"):
    if not data_escolhida:
        st.warning("⚠️ Por favor, selecione uma data!")
    else:
        data_formatada = data_escolhida.strftime("%d/%m/%y")  # Converte data para formato correto
        st.write(f"🔎 Buscando pautas para {data_formatada}...")

        with st.spinner("🔎 Buscando Sessão Deliberativa..."):
            sessao_url = buscar_sessao_deliberativa(data_formatada)
        
        if sessao_url:
            st.success(f"✅ Sessão encontrada: [{sessao_url}]({sessao_url})")
        else:
            st.error("⚠️ Nenhuma Sessão Deliberativa encontrada para essa data.")
