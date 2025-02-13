import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# 🛠 Configuração do WebDriver
chrome_driver_path = r"C:\webcrawler\chromedriver-win64\chromedriver.exe"
options = Options()
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
service = Service(executable_path=chrome_driver_path)

# 📌 Função para buscar a Sessão Deliberativa do dia
def buscar_sessao_deliberativa(data_final_formatada):
    driver = webdriver.Chrome(service=service, options=options)
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

# 📌 Função para acessar a sessão e buscar propostas
def acessar_sessao_e_abrir_propostas(sessao_url):
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(sessao_url)
    time.sleep(3)

    print("🔎 Rolando até a seção de Propostas...")

    try:
        for _ in range(15):  
            driver.execute_script("window.scrollBy(0, 200);")
            time.sleep(0.3)

        # 📌 Clicar nos botões "abrir"
        try:
            botao_analisadas = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="main-content"]/section[2]/div/div[1]/button/span'))
            )
            driver.execute_script("arguments[0].scrollIntoView();", botao_analisadas)
            botao_analisadas.click()
            time.sleep(3)

        except:
            pass

        try:
            botao_nao_analisadas = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="main-content"]/section[3]/div/div[1]/button/span'))
            )
            driver.execute_script("arguments[0].scrollIntoView();", botao_nao_analisadas)
            botao_nao_analisadas.click()
            time.sleep(3)

        except:
            pass

    except:
        pass

    propostas = {"analisadas": [], "nao_analisadas": []}

    try:
        propostas_analisadas = driver.find_elements(By.XPATH, '//*[@id="bloco-ja-analisados"]/ul/li')

        if propostas_analisadas:
            for proposta in propostas_analisadas:
                texto = proposta.text.strip().replace("PASSO A PASSO", "").replace("abrir", "").strip()
                try:
                    link = proposta.find_element(By.TAG_NAME, "a").get_attribute("href")
                except:
                    link = "#"
                propostas["analisadas"].append((texto, link))

        propostas_nao_analisadas = driver.find_elements(By.XPATH, '//*[@id="bloco-por-analisar"]/ul/li')

        if propostas_nao_analisadas:
            for proposta in propostas_nao_analisadas:
                texto = proposta.text.strip().replace("PASSO A PASSO", "").replace("abrir", "").strip()
                try:
                    link = proposta.find_element(By.TAG_NAME, "a").get_attribute("href")
                except:
                    link = "#"
                propostas["nao_analisadas"].append((texto, link))

    except:
        pass

    driver.quit()
    return propostas

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
            propostas = acessar_sessao_e_abrir_propostas(sessao_url)

            if propostas:
                # 📜 Mostrar Propostas Analisadas
                st.subheader("📜 Propostas Analisadas")
                if propostas["analisadas"]:
                    for proposta, link in propostas["analisadas"]:
                        st.markdown(f"- [{proposta}]({link})")
                else:
                    st.warning("⚠️ Nenhuma proposta analisada encontrada.")

                # ⚠️ Mostrar Propostas Não Analisadas
                st.subheader("⚠️ Propostas Não Analisadas")
                if propostas["nao_analisadas"]:
                    for proposta, link in propostas["nao_analisadas"]:
                        st.markdown(f"- [{proposta}]({link})")
                else:
                    st.success("✅ Todas as propostas foram analisadas!")
        else:
            st.error("⚠️ Nenhuma Sessão Deliberativa encontrada para essa data.")
