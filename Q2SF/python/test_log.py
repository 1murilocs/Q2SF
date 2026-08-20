import os
import datetime

log_dir = r"C:\Users\Murilo Santos\Desktop\Projetos\retorno quiver\update logs"
os.makedirs(log_dir, exist_ok=True)

timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = os.path.join(log_dir, f"update_log_{timestamp}.txt")

with open(log_filename, 'w', encoding='utf-8') as f_log:
    f_log.write(f"Relatorio de Atualizacao - {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
    f_log.write("="*50 + "\n\n")
