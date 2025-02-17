import tkinter as tk
from tkinter import messagebox
from tkcalendar import Calendar
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import webbrowser

# 🛠 Configurar o ChromeDriver
chrome_driver_path = r"C:\webcrawler\chromedriver-win64\chromedriver.exe"

options = Options()
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

service = Service(executable_path=chrome_driver_path)
driver = webdriver.Chrome(service=service, options=options)

# 📌 Função para buscar a Sessão Deliberativa do dia
def buscar_sessao_deliberativa(data_final_formatada):
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
                print(f"✅ Sessão Deliberativa encontrada: {link_sessao}")
                return link_sessao

        print("⚠️ Nenhuma Sessão Deliberativa encontrada para essa data.")
        return None

    except Exception as e:
        print(f"⚠️ Erro ao buscar sessão para essa data: {e}")
        return None

# 📌 Função para acessar a sessão, rolar e clicar nos botões "abrir"
def acessar_sessao_e_abrir_propostas(sessao_url):
    driver.get(sessao_url)
    time.sleep(3)

    print("🔎 Rolando até a seção de Propostas...")

    try:
        for _ in range(15):  
            driver.execute_script("window.scrollBy(0, 200);")
            time.sleep(0.3)

        # 📌 Expandindo seções "abrir"
        botoes_xpath = [
            '//*[@id="main-content"]/section[1]/div/div[1]/button/span',  # Propostas Previstas
            '//*[@id="main-content"]/section[2]/div/div[1]/button/span',  # Propostas Analisadas
            '//*[@id="main-content"]/section[3]/div/div[1]/button/span'   # Propostas Não Analisadas
        ]

        for xpath in botoes_xpath:
            try:
                botao = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                driver.execute_script("arguments[0].scrollIntoView();", botao)
                botao.click()
                time.sleep(3)
            except:
                pass

        print("✅ Todas as seções foram expandidas!")

    except Exception as e:
        print(f"⚠️ Erro ao rolar até as propostas: {e}")

    return buscar_propostas(sessao_url)

# 📌 Função para buscar propostas previstas, analisadas e não analisadas
def buscar_propostas(sessao_url):
    print("\n📜 Buscando Propostas...")

    propostas = {"previstas": [], "analisadas": [], "nao_analisadas": []}

    categorias = {
        "previstas": '//*[@id="bloco-previstos"]/ul/li',
        "analisadas": '//*[@id="bloco-ja-analisados"]/ul/li',
        "nao_analisadas": '//*[@id="bloco-por-analisar"]/ul/li'
    }

    for categoria, xpath in categorias.items():
        try:
            elementos = driver.find_elements(By.XPATH, xpath)

            if elementos:
                print(f"✅ {len(elementos)} propostas {categoria} encontradas.")
                for proposta in elementos:
                    texto = proposta.text.strip()
                    texto = texto.replace("PASSO A PASSO", "").replace("abrir", "").strip()

                    try:
                        link = proposta.find_element(By.TAG_NAME, "a").get_attribute("href")
                    except:
                        link = "#"

                    if texto:
                        propostas[categoria].append((texto, link))
            else:
                print(f"⚠️ Nenhuma proposta {categoria} encontrada.")

        except Exception as e:
            print(f"⚠️ Erro ao capturar propostas {categoria}: {e}")

    return gerar_pagina_html(propostas, sessao_url)

# 📌 Criar página HTML para exibir os resultados
def gerar_pagina_html(propostas, link):
    file_path = "pauta_sessao.html"

    if not any(propostas.values()):  # Se todas as categorias estiverem vazias
        html = f"""
        <html>
        <head>
            <title>Propostas da Sessão</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                }}
                h1 {{
                    color: red;
                    font-weight: 600;
                }}
            </style>
        </head>
        <body>
            <h1>⚠️ Nenhuma Sessão Deliberativa encontrada para essa data.</h1>
        </body>
        </html>
        """
    else:
        html = f"""
        <html>
        <head>
            <title>Propostas da Sessão</title>
            <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600&display=swap" rel="stylesheet">
            <style>
                body {{
                    font-family: 'Montserrat', sans-serif;
                    margin: 20px;
                }}
                h1 {{
                    color: #0073e6;
                    font-weight: 600;
                }}
                h2 {{
                    color: #ff6600;
                    font-weight: 400;
                }}
                ul {{
                    list-style-type: none;
                    padding: 0;
                }}
                li {{
                    margin-bottom: 10px;
                    padding: 10px;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    background-color: #f9f9f9;
                    font-weight: 300;
                }}
                a {{
                    color: #0073e6;
                    text-decoration: none;
                    font-weight: 400;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
            </style>
        </head>
        <body>
            <h1>Propostas da Sessão</h1>
            <p><a href="{link}" target="_blank">🔗 Acesse a Sessão</a></p>
        """

        for categoria, titulo in [("previstas", "📜 Propostas Previstas"), 
                                  ("analisadas", "📜 Propostas Analisadas"), 
                                  ("nao_analisadas", "⚠️ Propostas Não Analisadas")]:
            if propostas[categoria]:  # Só adiciona a seção se houver propostas
                html += f"<h2>{titulo}</h2><ul>"
                for texto, link in propostas[categoria]:
                    html += f'<li><a href="{link}" target="_blank">{texto}</a></li>'
                html += "</ul>"

        html += "</body></html>"

    with open(file_path, "w", encoding="utf-8") as file:
        file.write(html)

    webbrowser.open(file_path)

# 📌 Criar a interface gráfica do calendário
def abrir_calendario():
    def buscar_dados():
        data_final_formatada = cal.get_date()
        print(f"🔎 Buscando Sessão Deliberativa para {data_final_formatada}...")
        sessao_link = buscar_sessao_deliberativa(data_final_formatada)

        if sessao_link:
            acessar_sessao_e_abrir_propostas(sessao_link)
        else:
            messagebox.showwarning("Aviso", "⚠️ Nenhuma Sessão Deliberativa encontrada para essa data.")

    root = tk.Tk()
    root.title("Selecione a Data da Pauta")

    cal = Calendar(root, selectmode="day", date_pattern="dd/mm/yyyy", locale="pt_BR")  
    cal.pack(pady=20)

    btn = tk.Button(root, text="Buscar Sessão", command=buscar_dados)
    btn.pack(pady=10)

    root.mainloop()

abrir_calendario()
driver.quit()
