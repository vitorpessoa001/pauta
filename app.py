import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# 🛠 Configuração do WebDriver (movido para fora das funções para melhor performance)
options = Options()
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

#  Update Service initialization:
service = Service(executable_path="./chromedriver")  # For Linux/macOS
# or
# service = Service(executable_path="./chromedriver.exe")  # For Windows


# 📌 Função para buscar a Sessão Deliberativa do dia
@st.cache_data  # Cache para evitar buscas repetidas
def buscar_sessao_deliberativa(data_final_formatada):
    driver = webdriver.Chrome(service=service, options=options)
    try:
        url_agenda = f"https://www.camara.leg.br/agenda?dataInicial={data_final_formatada}&dataFinal={data_final_formatada}&categorias=Plen%C3%A1rio"
        driver.get(url_agenda)
        time.sleep(3)

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
    except Exception as e:
        st.error(f"Erro ao buscar sessão: {e}") # Exibe o erro no Streamlit
        driver.quit()
        return None


# 📌 Função para acessar a sessão e buscar propostas
@st.cache_data  # Cache para evitar buscas repetidas
def acessar_sessao_e_abrir_propostas(sessao_url):
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.get(sessao_url)
        time.sleep(3)

        # Rolar e clicar nos botões "abrir" (melhorado com WebDriverWait e tratamento de exceções)
        for xpath in [
            '//*[@id="main-content"]/section[2]/div/div[1]/button/span',  # Propostas Analisadas
            '//*[@id="main-content"]/section[3]/div/div[1]/button/span'   # Propostas Não Analisadas
        ]:
            try:
              botao = WebDriverWait(driver, 10).until(
                  EC.element_to_be_clickable((By.XPATH, xpath))
              )
              driver.execute_script("arguments[0].scrollIntoView();", botao) #Rola até o botão
              botao.click()
              time.sleep(3)
            except Exception as e:
                st.warning(f"Erro ao expandir seção: {e}") # Exibe o erro no Streamlit
                pass #Ignora o erro e continua para a próxima seção

        propostas = {"analisadas": [], "nao_analisadas": []}
        for categoria, xpath in [("analisadas", '//*[@id="bloco-ja-analisados"]/ul/li'), ("nao_analisadas", '//*[@id="bloco-por-analisar"]/ul/li')]:
            try:
                elementos = driver.find_elements(By.XPATH, xpath)
                for proposta in elementos:
                    texto = proposta.text.strip().replace("PASSO A PASSO", "").replace("abrir", "").strip()
                    try:
                        link = proposta.find_element(By.TAG_NAME, "a").get_attribute("href")
                    except:
                        link = "#"
                    propostas[categoria].append((texto, link))
            except Exception as e:
                st.error(f"Erro ao capturar propostas {categoria}: {e}") # Exibe o erro no Streamlit

        driver.quit()
        return propostas
    except Exception as e:
        st.error(f"Erro geral na função acessar_sessao_e_abrir_propostas: {e}")
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
        with st.spinner(f"Buscando pautas para {data_formatada}..."): #Spinner enquanto carrega
            sessao_url = buscar_sessao_deliberativa(data_formatada)

            if sessao_url:
                st.success(f"✅ Sessão encontrada: [{sessao_url}]({sessao_url})") #Link clicável
                propostas = acessar_sessao_e_abrir_propostas(sessao_url)

                if propostas:
                    for categoria, titulo in [("analisadas", "📜 Propostas Analisadas"), ("nao_analisadas", "⚠️ Propostas Não Analisadas")]:
                        st.subheader(titulo)
                        if propostas[categoria]:
                            for proposta, link in propostas[categoria]:
                                st.markdown(f"- [{proposta}]({link})") #Link clicável
                        else:
                            st.info(f"Nenhuma proposta {categoria} encontrada.") #Mensagem informativa
            else:
                st.error("⚠️ Nenhuma Sessão Deliberativa encontrada para essa data.")
