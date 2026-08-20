from cfg import PASSWORD
import re
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def send_email():
    # Lê o arquivo de log e extrai as linhas com links
    with open('insert_logs/apolices_distintas.log', 'r') as f:
        linhas = f.readlines()

    data_log = linhas[0].strip() if len(linhas) > 0 else ""
    linhas_com_link = [linha.strip().strip('- ') for linha in linhas if 'http' in linha]

    # HTML template
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
    body {{ font-family: Arial, sans-serif; background-color: #f4f4f9; color: #333; margin: 0; padding: 0; }}
    .container {{ width: 80%; max-width: 600px; margin: 20px auto; background-color: #fff; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); overflow: hidden; }}
    .header {{ background-color: #003E6B; color: #fff; padding: 20px; text-align: center; }}
    .content {{ padding: 20px; }}
    .url-list {{ list-style-type: none; padding: 0; }}
    .url-list li {{ background-color: #f8f9fa; margin: 10px 0; padding: 10px; border-left: 4px solid #003E6B; border-radius: 4px; word-break: break-all; }}
    .url-list a {{ color: #003E6B; text-decoration: none; font-weight: bold; font-size: 14px; }}
    .url-list a:hover {{ text-decoration: underline; }}
    .footer {{ background-color: #f1f1f1; color: #777; text-align: center; padding: 10px; font-size: 12px; }}
    </style>
    </head>
    <body>
    <div class="header">
        <h2>Alerta: Apólices Distintas</h2>
    </div>
    <p style="font-size: 14px;">As seguintes oportunidades têm apólices distintas <strong>NO QUIVER</strong> contendo a mesma proposta.</p>
    <p style="font-size: 14px;">Acesse os links abaixo para verificar as oportunidades no Salesforce e realizar as mudanças necessárias no Quiver:</p>
    <ul class="url-list">"""
    for linha in linhas_com_link:
        match = re.search(r'(https?://\S+)', linha)
        if match:
            url = match.group(1)
            texto_extra = linha.replace(url, '').strip(' -')
            if texto_extra:
                html += f'                <li><a href="{url}">{url}</a> — {texto_extra}</li>\n'
            else:
                html += f'                <li><a href="{url}">{url}</a></li>\n'
    html += """
                </ul>
            </div>
            <div class="footer">Este é um e-mail automático sobre o retorno Quiver-Salesforce.</div>
        </div>
    </body>
    </html>"""

    #configurações do e-mail
    sender = 'murilo.santos@galcorr.com.br'
    receivers = ['marcos.yamaguti@galcorr.com.br', 'murilo.santos@galcorr.com.br']
    password = PASSWORD

    #conteúdo do e-mail
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = ', '.join(receivers)  # Juntar todos os destinatários em uma string
    msg['Subject'] = 'Retorno Quiver: Apólices Distintas Encontradas'

    msg.attach(MIMEText(html, 'html'))

    try:
        print('Conectando ao servidor...')
        server = smtplib.SMTP('smtp.outlook.com', 587)
        server.starttls() #incializa a conexão segura
        server.login(sender, password)
        server.sendmail(sender, receivers, msg.as_string())
        print('E-mail enviado com sucesso!') 
    except Exception as e:
        print(f'Erro ao enviar e-mail: {e}')
    finally:    
        server.quit()