import base64
import os
from datetime import datetime
import weasyprint

def _obter_logo_base64_local() -> str:
    """Busca a logo local na pasta de serviços para embutir no PDF"""
    nome_logo = "flamboyant-logo.png"
    caminho_logo = os.path.join(os.path.dirname(__file__), nome_logo)
    
    if os.path.exists(caminho_logo):
        try:
            with open(caminho_logo, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
                return f"data:image/png;base64,{encoded_string}"
        except Exception:
            pass
    return ""

def gerar_pdf_dossie_loja(dados_loja: dict, period: dict, historico_treinamentos: list) -> bytes:
    """
    Gera o PDF do Dossiê da Loja por Período usando WeasyPrint.
    historico_treinamentos: lista de dicts contendo:
      - tema: str
      - data: str
      - presentes: lista de str (nomes de representantes presentes)
      - ausentes: lista de str (nomes de representantes ausentes/pendentes)
    """
    logo_src = _obter_logo_base64_local()
    elemento_logo = f'<img src="{logo_src}" style="display: block; width: 130px; height: auto; border: 0;" alt="Flamboyant" />' if logo_src else ""
    
    total_treinamentos = len(historico_treinamentos)
    
    # Calcular estatísticas globais
    total_presencas = 0
    total_ausencias = 0
    for t in historico_treinamentos:
        total_presencas += len(t.get("presentes", []))
        total_ausencias += len(t.get("ausentes", []))
    
    total_convocacoes = total_presencas + total_ausencias
    taxa_presenca = round((total_presencas / total_convocacoes) * 100) if total_convocacoes > 0 else 0
    
    linhas_tabela = []
    for idx, t in enumerate(historico_treinamentos):
        lista_presentes = ", ".join(t.get("presentes", [])) or "Nenhum"
        lista_ausentes = ", ".join(t.get("ausentes", [])) or "Nenhum"
        
        linhas_tabela.append(f"""
            <tr>
                <td style="padding: 12px 15px; border-bottom: 1px solid #E5E7EB; vertical-align: top; width: 40%;">
                    <div style="font-weight: 700; color: #1F2937; font-size: 12.5px;">{t.get('tema')}</div>
                    <div style="font-size: 11px; color: #6B7280; margin-top: 3px;">{t.get('data')}</div>
                </td>
                <td style="padding: 12px 15px; border-bottom: 1px solid #E5E7EB; vertical-align: top; color: #10B981; font-weight: 500; width: 30%;">
                    {lista_presentes}
                </td>
                <td style="padding: 12px 15px; border-bottom: 1px solid #E5E7EB; vertical-align: top; color: #D93030; font-weight: 500; width: 30%;">
                    {lista_ausentes}
                </td>
            </tr>
        """)
        
    html_linhas = "".join(linhas_tabela)

    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <title>Dossiê de Loja - {dados_loja.get('nome')}</title>
    <style>
        @page {{
            size: A4;
            margin: 0; /* Sangria total na folha A4 */
        }}
        *, *::before, *::after {{
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Inter', 'Roboto', system-ui, sans-serif;
            color: #1F2937;
            font-size: 13px;
            line-height: 1.5;
            background-color: #F7F4EF;
            margin: 0;
            padding: 0;
            width: 100%;
        }}
        
        /* Margem de segurança controlada via CSS para o fundo bege respirar */
        .page-wrapper {{
            padding: 18mm 16mm;
            width: 100%;
        }}

        /* Card Principal com a mesma UI do Email */
        .main-card {{
            background-color: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            width: 100%;
        }}

        /* Cabeçalho Idêntico ao do Email */
        .brand-header {{
            background-color: #8B1A1A;
            padding: 25px 30px;
            border-bottom: 4px solid #C8A882;
        }}
        .header-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .header-title-text {{
            color: #C8A882;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 2px;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        .header-main-heading {{
            margin: 0;
            color: #FFFFFF;
            font-size: 20px;
            font-weight: 700;
            line-height: 1.3;
        }}

        /* Conteúdo Interno */
        .card-body {{
            padding: 30px;
        }}
        
        .secao-titulo {{
            color: #8B1A1A;
            font-size: 12px;
            text-transform: uppercase;
            font-weight: 700;
            margin-bottom: 12px;
            letter-spacing: 0.5px;
        }}

        /* Estruturas em tabela para compatibilidade WeasyPrint (evita quebra de floats) */
        .layout-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 25px;
        }}
        .info-block-cell {{
            background-color: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 6px;
            padding: 18px;
            vertical-align: top;
        }}

        .tabela-container {{
            background-color: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 6px;
            overflow: hidden;
            margin-bottom: 25px;
            width: 100%;
        }}
        table.dados-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th {{
            background-color: #F9FAFB;
            color: #1F2937;
            font-weight: 700;
            text-transform: uppercase;
            font-size: 10.5px;
            letter-spacing: 0.5px;
            padding: 12px 15px;
            border-bottom: 2px solid #E5E7EB;
            text-align: left;
        }}
        tr {{
            page-break-inside: avoid;
        }}
        .footer-nota {{
            margin-top: 40px;
            text-align: center;
            font-size: 11px;
            color: #9CA3AF;
            border-top: 1px solid #E5E7EB;
            padding-top: 18px;
            page-break-inside: avoid;
        }}
    </style>
</head>
<body>

    <div class="page-wrapper">
        <div class="main-card">
            
            <div class="brand-header">
                <table class="header-table">
                    <tr>
                        <td style="padding: 0; vertical-align: middle; text-align: left; width: 140px;">
                            {elemento_logo}
                        </td>
                        <td style="padding: 0; vertical-align: middle; text-align: right;">
                            <div class="header-title-text">Gestão de T&D Corporativo</div>
                            <h1 class="header-main-heading">Dossiê de Performance Consolidado</h1>
                        </td>
                    </tr>
                </table>
            </div>

            <div class="card-body">
                
                <table class="layout-table">
                    <tr>
                        <td class="info-block-cell" style="width: 100%;">
                            <div class="secao-titulo">Identificação da Unidade</div>
                            <table style="width: 100%; font-size: 13px; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 5px 0; font-weight: 700; color: #1F2937; width: 15%;">Parceiro / Loja:</td>
                                    <td style="padding: 5px 0; color: #4B5563; font-weight: 600;">{dados_loja.get('nome')}</td>
                                    <td style="padding: 5px 0; font-weight: 700; color: #1F2937; width: 15%;">Período Analisado:</td>
                                    <td style="padding: 5px 0; color: #4B5563;">{period.get('de')} até {period.get('ate')}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 5px 0; font-weight: 700; color: #1F2937;">Segmentação:</td>
                                    <td style="padding: 5px 0; color: #4B5563;">{dados_loja.get('segmento', 'Lojas')}</td>
                                    <td style="padding: 5px 0; font-weight: 700; color: #1F2937;">Total Módulos:</td>
                                    <td style="padding: 5px 0; color: #4B5563; font-weight: 600;">{total_treinamentos} evento(s)</td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>

                <table class="layout-table">
                    <tr>
                        <td class="info-block-cell" style="width: 48%;">
                            <div class="secao-titulo">Performance de Presença</div>
                            <div style="font-size: 32px; font-weight: 800; color: #8B1A1A; line-height: 1;">{taxa_presenca}%</div>
                            <div style="font-size: 11.5px; color: #6B7280; margin-top: 4px;">Taxa Geral de Frequência da Loja</div>
                        </td>
                        <td style="width: 4%;"></td>
                        <td class="info-block-cell" style="width: 48%;">
                            <div class="secao-titulo">Auditoria Balanceada</div>
                            <div style="font-size: 32px; font-weight: 800; color: #1F2937; line-height: 1;">{total_presencas} <span style="font-size: 16px; color: #9CA3AF; font-weight: 400;">/ {total_convocacoes}</span></div>
                            <div style="font-size: 11.5px; color: #6B7280; margin-top: 4px;">Total de Check-ins Efetuados com Sucesso</div>
                        </td>
                    </tr>
                </table>

                <div class="secao-titulo" style="margin-top: 10px;">Histórico Nominal Crônico por Evento</div>
                <div class="tabela-container">
                    <table class="dados-table">
                        <thead>
                            <tr>
                                <th style="width: 40%;">Módulo Corporativo / Data</th>
                                <th style="width: 30%;">Representantes Presentes</th>
                                <th style="width: 30%;">Ausentes ou Pendentes</th>
                            </tr>
                        </thead>
                        <tbody>
                            {html_linhas if html_linhas else '<tr><td colspan="3" style="padding: 15px; text-align: center; color: #6B7280;">Nenhum registro encontrado no período informado.</td></tr>'}
                        </tbody>
                    </table>
                </div>

                <div class="footer-nota">
                    <div style="font-weight: 700; color: #8B1A1A; text-transform: uppercase; margin-bottom: 2px;">Grupo Flamboyant — Centro de Treinamento e Desenvolvimento</div>
                    <div>Relatório Executivo Oficial gerado eletronicamente em {datetime.now().strftime('%d/%m/%Y às %H:%M')}.</div>
                </div>

            </div>
        </div>
    </div>

</body>
</html>"""

    return weasyprint.HTML(string=html_content).write_pdf()


def gerar_pdf_ata_chamada(dados_treinamento: dict, presentes: list, ausentes: list) -> bytes:
    """
    Gera o PDF da Lista de Chamada do Treinamento usando WeasyPrint.
    presentes: lista de dicts contendo {"nome": str, "cargo": str, "loja": str, "horario": str}
    ausentes: lista de dicts contendo {"nome": str, "cargo": str, "loja": str}
    """
    logo_src = _obter_logo_base64_local()
    elemento_logo = f'<img src="{logo_src}" style="display: block; width: 130px; height: auto; border: 0;" alt="Flamboyant" />' if logo_src else ""
    
    total_convocados = len(presentes) + len(ausentes)
    total_presentes = len(presentes)
    taxa_presenca = round((total_presentes / total_convocados) * 100) if total_convocados > 0 else 0
    
    linhas_presentes = []
    for p in presentes:
        linhas_presentes.append(f"""
            <tr>
                <td style="padding: 11px 15px; border-bottom: 1px solid #E5E7EB; width: 45%;">
                    <div style="font-weight: 600; color: #1F2937; font-size: 12.5px;">{p.get('nome')}</div>
                    <div style="font-size: 11px; color: #6B7280; margin-top: 1px;">{p.get('cargo', 'Colaborador')}</div>
                </td>
                <td style="padding: 11px 15px; border-bottom: 1px solid #E5E7EB; color: #4B5563; width: 35%; font-weight: 500;">{p.get('loja')}</td>
                <td style="padding: 11px 15px; border-bottom: 1px solid #E5E7EB; color: #10B981; font-weight: 600; text-align: right; width: 20%;">
                    {p.get('horario', '--:--')}
                </td>
            </tr>
        """)

    linhas_ausentes = []
    for a in ausentes:
        linhas_ausentes.append(f"""
            <tr>
                <td style="padding: 11px 15px; border-bottom: 1px solid #E5E7EB; width: 45%;">
                    <div style="font-weight: 600; color: #1F2937; font-size: 12.5px;">{a.get('nome')}</div>
                    <div style="font-size: 11px; color: #6B7280; margin-top: 1px;">{a.get('cargo', 'Colaborador')}</div>
                </td>
                <td style="padding: 11px 15px; border-bottom: 1px solid #E5E7EB; color: #4B5563; width: 35%; font-weight: 500;">{a.get('loja')}</td>
                <td style="padding: 11px 15px; border-bottom: 1px solid #E5E7EB; color: #D93030; font-weight: 600; text-align: right; width: 20%;">
                    Ausente
                </td>
            </tr>
        """)

    html_presentes = "".join(linhas_presentes)
    html_ausentes = "".join(linhas_ausentes)

    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <title>Ata de Presença - {dados_treinamento.get('tema')}</title>
    <style>
        @page {{
            size: A4;
            margin: 0; /* Garante o preenchimento absoluto do background bege */
        }}
        *, *::before, *::after {{
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Inter', 'Roboto', system-ui, sans-serif;
            color: #1F2937;
            font-size: 13px;
            line-height: 1.5;
            background-color: #F7F4EF;
            margin: 0;
            padding: 0;
            width: 100%;
        }}
        
        .page-wrapper {{
            padding: 18mm 16mm;
            width: 100%;
        }}

        .main-card {{
            background-color: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            width: 100%;
        }}

        .brand-header {{
            background-color: #8B1A1A;
            padding: 25px 30px;
            border-bottom: 4px solid #C8A882;
        }}
        .header-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .header-title-text {{
            color: #C8A882;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 2px;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        .header-main-heading {{
            margin: 0;
            color: #FFFFFF;
            font-size: 20px;
            font-weight: 700;
            line-height: 1.3;
        }}

        .card-body {{
            padding: 30px;
        }}
        
        .secao-titulo {{
            color: #8B1A1A;
            font-size: 12px;
            text-transform: uppercase;
            font-weight: 700;
            margin-bottom: 12px;
            letter-spacing: 0.5px;
        }}

        .layout-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 25px;
        }}
        .info-block-cell {{
            background-color: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 6px;
            padding: 18px;
            vertical-align: top;
        }}

        .tabela-container {{
            background-color: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 6px;
            overflow: hidden;
            margin-bottom: 25px;
            width: 100%;
        }}
        table.dados-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th {{
            background-color: #F9FAFB;
            color: #1F2937;
            font-weight: 700;
            text-transform: uppercase;
            font-size: 10.5px;
            letter-spacing: 0.5px;
            padding: 12px 15px;
            border-bottom: 2px solid #E5E7EB;
            text-align: left;
        }}
        tr {{
            page-break-inside: avoid;
        }}
        .footer-nota {{
            margin-top: 40px;
            text-align: center;
            font-size: 11px;
            color: #9CA3AF;
            border-top: 1px solid #E5E7EB;
            padding-top: 18px;
            page-break-inside: avoid;
        }}
    </style>
</head>
<body>

    <div class="page-wrapper">
        <div class="main-card">
            
            <div class="brand-header">
                <table class="header-table">
                    <tr>
                        <td style="padding: 0; vertical-align: middle; text-align: left; width: 140px;">
                            {elemento_logo}
                        </td>
                        <td style="padding: 0; vertical-align: middle; text-align: right;">
                            <div class="header-title-text">Gestão de T&D Corporativo</div>
                            <h1 class="header-main-heading">Lista de Chamada Oficial</h1>
                        </td>
                    </tr>
                </table>
            </div>

            <div class="card-body">
                
                <table class="layout-table">
                    <tr>
                        <td class="info-block-cell" style="width: 100%;">
                            <div class="secao-titulo">Dados Gerais do Treinamento</div>
                            <table style="width: 100%; font-size: 13px; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 5px 0; font-weight: 700; color: #1F2937; width: 18%;">Tema:</td>
                                    <td style="padding: 5px 0; color: #4B5563; font-weight: 600; width: 32%;">{dados_treinamento.get('tema')}</td>
                                    <td style="padding: 5px 0; font-weight: 700; color: #1F2937; width: 15%;">Data/Hora:</td>
                                    <td style="padding: 5px 0; color: #4B5563; width: 35%;">{dados_treinamento.get('data')} às {dados_treinamento.get('hora')}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 5px 0; font-weight: 700; color: #1F2937;">Facilitador:</td>
                                    <td style="padding: 5px 0; color: #4B5563;">{dados_treinamento.get('instrutor', 'Não Informado')}</td>
                                    <td style="padding: 5px 0; font-weight: 700; color: #1F2937;">Local:</td>
                                    <td style="padding: 5px 0; color: #4B5563;">{dados_treinamento.get('local')}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 5px 0; font-weight: 700; color: #1F2937;">Carga Horária:</td>
                                    <td style="padding: 5px 0; color: #4B5563;">{dados_treinamento.get('carga_horaria', 'N/A')}</td>
                                    <td style="padding: 5px 0; font-weight: 700; color: #1F2937;">Segmento Alvo:</td>
                                    <td style="padding: 5px 0; color: #4B5563;">{dados_treinamento.get('segmento_alvo')}</td>
                            </table>
                        </td>
                    </tr>
                </table>

                <table class="layout-table">
                    <tr>
                        <td class="info-block-cell" style="width: 48%;">
                            <div class="secao-titulo">Performance de Presença</div>
                            <div style="font-size: 32px; font-weight: 800; color: #8B1A1A; line-height: 1;">{taxa_presenca}%</div>
                            <div style="font-size: 11.5px; color: #6B7280; margin-top: 4px;">Taxa Geral de Frequência</div>
                        </td>
                        <td style="width: 4%;"></td>
                        <td class="info-block-cell" style="width: 48%;">
                            <div class="secao-titulo">Auditoria de Vagas</div>
                            <div style="font-size: 32px; font-weight: 800; color: #1F2937; line-height: 1;">{total_presentes} <span style="font-size: 16px; color: #9CA3AF; font-weight: 400;">/ {total_convocados}</span></div>
                            <div style="font-size: 11.5px; color: #6B7280; margin-top: 4px;">Presentes vs. Total Convocados</div>
                        </td>
                    </tr>
                </table>

                <div class="secao-titulo" style="margin-top: 10px;">Representantes Presentes</div>
                <div class="tabela-container">
                    <table class="dados-table">
                        <thead>
                            <tr>
                                <th style="width: 45%;">Nome / Cargo</th>
                                <th style="width: 35%;">Franquia / Loja</th>
                                <th style="width: 20%; text-align: right;">Horário Check-in</th>
                            </tr>
                        </thead>
                        <tbody>
                            {html_presentes if html_presentes else '<tr><td colspan="3" style="padding: 15px; text-align: center; color: #6B7280;">Nenhum participante confirmado como presente.</td></tr>'}
                        </tbody>
                    </table>
                </div>

                <div class="secao-titulo" style="margin-top: 15px;">Representantes Ausentes / Pendentes</div>
                <div class="tabela-container">
                    <table class="dados-table">
                        <thead>
                            <tr>
                                <th style="width: 45%;">Nome / Cargo</th>
                                <th style="width: 35%;">Franquia / Loja</th>
                                <th style="width: 20%; text-align: right;">Situação</th>
                            </tr>
                        </thead>
                        <tbody>
                            {html_ausentes if html_ausentes else '<tr><td colspan="3" style="padding: 15px; text-align: center; color: #6B7280;">Nenhum participante ausente.</td></tr>'}
                        </tbody>
                    </table>
                </div>

                <div class="footer-nota">
                    <div style="font-weight: 700; color: #8B1A1A; text-transform: uppercase; margin-bottom: 2px;">Grupo Flamboyant — Centro de Treinamento e Desenvolvimento</div>
                    <div>Ata Oficial gerada de forma automatizada em {datetime.now().strftime('%d/%m/%Y às %H:%M')}.</div>
                </div>

            </div>
        </div>
    </div>

</body>
</html>"""

    return weasyprint.HTML(string=html_content).write_pdf()