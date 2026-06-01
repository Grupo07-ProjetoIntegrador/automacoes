import base64
import os
from datetime import datetime

try:
    import pdfkit
    PDFKIT_DISPONIVEL = True
except ImportError:
    PDFKIT_DISPONIVEL = False


def _obter_logo_base64_local() -> str:
    """Busca a logo local na pasta de serviços para embutir no PDF"""
    # Procura especificamente pelo arquivo na mesma pasta do script
    nome_logo = "flamboyant-logo.png"
    caminho_logo = os.path.join(os.path.dirname(__file__), nome_logo)
    
    if os.path.exists(caminho_logo):
        try:
            with open(caminho_logo, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
                return f"data:image/png;base64,{encoded_string}"
        except Exception as e:
            print(f"⚠ Erro ao ler o arquivo de imagem: {e}")
    else:
        print(f"ℹ Nota: O arquivo '{nome_logo}' não foi encontrado em '{os.path.dirname(__file__)}'. Usando texto alternativo.")
    return ""


def gerar_html_ata_presenca(dados_treinamento: dict, participantes: list) -> str:
    # Resgata o Base64 da logo
    logo_src = _obter_logo_base64_local()
    
    total_convocados = len(participantes)
    total_presentes = sum(1 for p in participantes if p.get('status', '').lower() == 'presente')
    total_ausentes = total_convocados - total_presentes
    
    taxa_presenca = round((total_presentes / total_convocados) * 100) if total_convocados > 0 else 0
    taxa_absenteismo = 100 - taxa_presenca

    linhas_tabela = []
    for p in participantes:
        status_limpo = p.get('status', 'Ausente').strip()
        is_presente = status_limpo.lower() == 'presente'
        
        badge_class = "badge-presente" if is_presente else "badge-ausente"
            
        linhas_tabela.append(f"""
            <tr>
                <td>
                    <div style="font-weight: 600; color: #1F2937;">{p.get('colaborador')}</div>
                    <div style="font-size: 11.5px; color: #6B7280; margin-top: 2px;">{p.get('cargo', 'Colaborador')}</div>
                </td>
                <td style="color: #4B5563; font-weight: 500;">{p.get('loja')}</td>
                <td style="text-align: center;">
                    <span class="badge {badge_class}">{status_limpo}</span>
                </td>
            </tr>
        """)

    html_linhas = "".join(linhas_tabela)

    # Renderização dinâmica do elemento da Logo no Cabeçalho
    # Se houver o Base64, ele joga a tag <img>, caso contrário, usa o texto de marca refinado.
    if logo_src:
        elemento_logo = f'<img src="{logo_src}" alt="Flamboyant" />'
    else:
        elemento_logo = '<div class="header-logo-text">FLAMBOYANT</div>'

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <title>Ata de Presença - {dados_treinamento.get('tema')}</title>
    <style>
        @page {{
            size: A4;
            margin: 18mm 15mm 18mm 15mm;
        }}
        * {{
            box-sizing: border-box;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }}
        body {{
            font-family: 'Inter', 'Roboto', system-ui, sans-serif;
            background-color: #F7F4EF;
            color: #1F2937;
            margin: 0;
            padding: 10px;
            font-size: 13.5px;
            line-height: 1.6;
        }}
        .header-container {{
            border-bottom: 2px solid #C8A882;
            padding-bottom: 20px;
            margin-bottom: 25px;
            display: table;
            width: 100%;
        }}
        .header-logo {{
            display: table-cell;
            vertical-align: bottom;
            width: 150px;
        }}
        .header-logo img {{
            display: block;
            max-width: 140px;
            height: auto;
            max-height: 45px;
        }}
        .header-logo-text {{
            font-size: 24px;
            font-weight: 800;
            color: #8B1A1A;
            letter-spacing: 2px;
        }}
        .header-title {{
            display: table-cell;
            text-align: right;
            vertical-align: bottom;
        }}
        .header-title h1 {{
            margin: 0;
            font-size: 20px;
            font-weight: 700;
            color: #1F2937;
            text-transform: uppercase;
            letter-spacing: -0.5px;
        }}
        .header-title span {{
            font-size: 11px;
            color: #C8A882;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1.5px;
        }}
        .info-grid {{
            display: table;
            width: 100%;
            margin-bottom: 25px;
            border-spacing: 16px 0;
            margin-left: -16px;
        }}
        .info-col {{
            display: table-cell;
            background-color: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 6px;
            padding: 22px;
            vertical-align: top;
            box-shadow: 0 1px 2px rgba(0,0,0,0.01);
        }}
        .secao-titulo {{
            margin-top: 0;
            margin-bottom: 14px;
            color: #8B1A1A;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            font-weight: 700;
        }}
        .tabela-container {{
            background-color: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 6px;
            overflow: hidden;
            margin-bottom: 30px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th {{
            background-color: #F9FAFB;
            color: #1F2937;
            font-weight: 700;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.5px;
            padding: 14px 20px;
            border-bottom: 2px solid #E5E7EB;
        }}
        td {{
            padding: 14px 20px;
            border-bottom: 1px solid #E5E7EB;
            vertical-align: middle;
        }}
        tr {{
            page-break-inside: avoid;
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .badge-presente {{
            background-color: rgba(16, 185, 129, 0.1);
            color: #10B981;
            border: 1px solid rgba(16, 185, 129, 0.2);
        }}
        .badge-ausente {{
            background-color: rgba(217, 48, 48, 0.1);
            color: #D93030;
            border: 1px solid rgba(217, 48, 48, 0.2);
        }}
        .diretriz-box {{
            border-left: 3px solid #8B1A1A;
            padding: 12px 16px;
            background-color: rgba(139, 26, 26, 0.03);
            margin-bottom: 25px;
            font-size: 12.5px;
            color: #4B5563;
        }}
        .footer-nota {{
            margin-top: 40px;
            text-align: center;
            font-size: 11px;
            color: #9CA3AF;
            border-top: 1px solid #E5E7EB;
            padding-top: 20px;
        }}
    </style>
</head>
<body>

    <div class="header-container">
        <div class="header-logo">
            {elemento_logo}
        </div>
        <div class="header-title">
            <span>Gestão de T&D Corporativo</span>
            <h1>Ata Oficial de Presença</h1>
        </div>
    </div>

    <div class="diretriz-box">
        <strong>Documento de Validação de Evento:</strong> Esta lista consolida a auditoria de presença imediata do módulo de treinamento corporativo citado abaixo. Os dados servem para comprovação de capacitação de franqueados e auditorias internas.
    </div>

    <div class="info-grid">
        <div class="info-col" style="width: 55%;">
            <div class="secao-titulo">Detalhes do Treinamento</div>
            <table style="width: 100%; font-size: 13px;">
                <tr>
                    <td style="padding: 4px 0; font-weight: 700; color: #1F2937; width: 30%; border: none;">Módulo / Tema:</td>
                    <td style="padding: 4px 0; border: none; color: #4B5563; font-weight: 600;">{dados_treinamento.get('tema')}</td>
                </tr>
                <tr>
                    <td style="padding: 4px 0; font-weight: 700; color: #1F2937; border: none;">Facilitador:</td>
                    <td style="padding: 4px 0; border: none; color: #4B5563;">{dados_treinamento.get('instrutor')}</td>
                </tr>
                <tr>
                    <td style="padding: 4px 0; font-weight: 700; color: #1F2937; border: none;">Data & Local:</td>
                    <td style="padding: 4px 0; border: none; color: #4B5563;">{dados_treinamento.get('data')} — {dados_treinamento.get('local')}</td>
                </tr>
                <tr>
                    <td style="padding: 4px 0; font-weight: 700; color: #1F2937; border: none;">Carga Horária:</td>
                    <td style="padding: 4px 0; border: none; color: #D93030; font-weight: 600;">{dados_treinamento.get('carga_horaria')}</td>
                </tr>
            </table>
        </div>

        <div class="info-col" style="width: 45%;">
            <div class="secao-titulo">Performance da Sessão</div>
            <div style="display: table; width: 100%; margin-top: 5px;">
                <div style="display: table-cell; width: 50%; vertical-align: middle;">
                    <div style="font-size: 36px; font-weight: 800; color: #8B1A1A; line-height: 1;">{taxa_presenca}%</div>
                    <div style="font-size: 11px; color: #6B7280; margin-top: 3px; font-style: italic;">Taxa de Presença</div>
                </div>
                <div style="display: table-cell; width: 50%; vertical-align: middle; padding-left: 15px; border-left: 1px solid #E5E7EB; font-size: 12px; color: #4B5563;">
                    <div style="margin-bottom: 3px;">Convocados: <strong>{total_convocados}</strong></div>
                    <div style="margin-bottom: 3px; color: #10B981;">Presentes: <strong>{total_presentes}</strong></div>
                    <div style="color: #D93030;">Faltas: <strong>{total_ausentes} ({taxa_absenteismo}%)</strong></div>
                </div>
            </div>
            <div style="width: 100%; background-color: #E5E7EB; height: 6px; border-radius: 3px; margin-top: 15px; overflow: hidden;">
                <div style="background-color: #8B1A1A; width: {taxa_presenca}%; height: 100%; border-radius: 3px;"></div>
            </div>
        </div>
    </div>

    <div style="color: #1F2937; font-size: 12px; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 700; margin-bottom: 10px;">
        Relação Nominal de Frequência (Multilojas)
    </div>
    
    <div class="tabela-container">
        <table>
            <thead>
                <tr>
                    <th style="text-align: left; width: 45%;">Profissional Convocado</th>
                    <th style="text-align: left; width: 40%;">Franquia / Loja Parceira</th>
                    <th style="text-align: center; width: 15%;">Frequência</th>
                </tr>
            </thead>
            <tbody>
                {html_linhas}
            </tbody>
        </table>
    </div>

    <div class="footer-nota">
        <div style="font-weight: 700; color: #8B1A1A; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px;">Grupo Flamboyant — Centro de Treinamento e Desenvolvimento</div>
        <div>Ata gerada de forma automatizada pelo ecossistema corporativo em {datetime.now().strftime('%d/%m/%Y às %H:%M')}.</div>
        <div style="font-style: italic; color: #C8A882; margin-top: 4px;">"Elevar para evoluir, envolver para encantar."</div>
    </div>

</body>
</html>"""


if __name__ == "__main__":
    treinamento_teste = {
        "tema": "Visual Merchandising & Encantamento de Clientes",
        "instrutor": "Profª. Mariana Alencastro (Consultora de Branding)",
        "data": "15/06/2026 às 09:00",
        "local": "Auditório Central - Piso 3",
        "carga_horaria": "4 horas"
    }
    
    participantes_teste = [
        {"colaborador": "Ana Júlia Almeida", "cargo": "Vendedora Líder", "loja": "Chilli Beans", "status": "Presente"},
        {"colaborador": "Marcos Roberto Costa", "cargo": "Gerente", "loja": "Chilli Beans", "status": "Presente"},
        {"colaborador": "Ricardo Souza Dias", "cargo": "Consultor", "loja": "Vivara", "status": "Presente"},
        {"colaborador": "Beatriz Viana Ramos", "cargo": "Lojista", "loja": "Reserva", "status": "Ausente"},
        {"colaborador": "Fernanda Lima Pires", "cargo": "Subgerente", "loja": "John John", "status": "Presente"},
        {"colaborador": "Thiago Martins Neves", "cargo": "Vendedor", "loja": "Vivara", "status": "Ausente"}
    ]

    html_final = gerar_html_ata_presenca(treinamento_teste, participantes_teste)
    
    nome_arquivo_html = "ata_presenca.html"
    with open(nome_arquivo_html, "w", encoding="utf-8") as f:
        f.write(html_final)
    print(f"✔ Sucesso! Arquivo '{nome_arquivo_html}' criado.")
    
    if PDFKIT_DISPONIVEL:
        nome_arquivo_pdf = "ata_presenca.pdf"
        try:
            # Caminho explícito do executável no Windows
            caminho_wkhtmltopdf = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
            config = pdfkit.configuration(wkhtmltopdf=caminho_wkhtmltopdf)
            
            opcoes = {
                'page-size': 'A4',
                'margin-top': '18mm',
                'margin-right': '15mm',
                'margin-bottom': '18mm',
                'margin-left': '15mm',
                'encoding': "UTF-8",
                'enable-local-file-access': None
            }
            
            pdfkit.from_string(html_final, nome_arquivo_pdf, options=opcoes, configuration=config)
            print(f"✔ PDF '{nome_arquivo_pdf}' gerado com sucesso!")
        except Exception as e:
            print(f"❌ Erro na conversão para PDF: {e}")
    else:
        print("ℹ Biblioteca 'pdfkit' não encontrada. Instale usando 'pip install pdfkit'")