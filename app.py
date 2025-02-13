import streamlit as st
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# 🛠 Configuração do WebDriver sem precisar baixar manualmente o ChromeDriver
def iniciar_driver():
    return uc.Chrome(headless=True)  # Rodar sem interface gráfica

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
                driver.quit()
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
data_escolhida = st.date_input("📅 Escolha uma data", format="DD/MM/YYYY")

# 📌 Botão para buscar a pauta
if st.button("🔍 Buscar Pauta"):
    if not data_escolhida:
        st.warning("⚠️ Por favor, selecione uma data!")
    else:
        data_formatada = data_escolhida.strftime("%d/%m/%y")
        st.write(f"🔎 Buscando pautas para {data_formatada}...")

        # Buscar sessão deliberativa
        sessao_url = buscar_sessao_deliberativa(data_formatada)
        
        if sessao_url:
            st.success(f"✅ Sessão encontrada: [{sessao_url}]({sessao_url})")
        else:
            st.error("⚠️ Nenhuma Sessão Deliberativa encontrada para essa data.")
