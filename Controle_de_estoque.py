import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import datetime
from fpdf import FPDF

# Tenta importar extras para visual bonito
try:
    from streamlit_extras.metric_cards import style_metric_cards

    USE_EXTRAS = True
except ImportError:
    USE_EXTRAS = False

# ==============================================================================
# 1. PARÂMETROS DE ENGENHARIA
# ==============================================================================

DENSIDADE_MENSAL = {
    1: {'Pinus': 580, 'Eucalipto': 820},
    2: {'Pinus': 580, 'Eucalipto': 820},
    3: {'Pinus': 560, 'Eucalipto': 790},
    4: {'Pinus': 540, 'Eucalipto': 760},
    5: {'Pinus': 520, 'Eucalipto': 740},
    6: {'Pinus': 500, 'Eucalipto': 720},
    7: {'Pinus': 500, 'Eucalipto': 710},
    8: {'Pinus': 490, 'Eucalipto': 700},
    9: {'Pinus': 510, 'Eucalipto': 730},
    10: {'Pinus': 530, 'Eucalipto': 760},
    11: {'Pinus': 550, 'Eucalipto': 780},
    12: {'Pinus': 570, 'Eucalipto': 800},
}

FATOR_ARRUMADO = {
    'Pinus': 0.65,
    'Eucalipto': 0.60
}

DB_FILE = 'estoque_arauco_final.json'


# ==============================================================================
# 2. GERAÇÃO DE PDF (COM LOGOTIPO)
# ==============================================================================

class PDFReport(FPDF):
    def header(self):
        # Verifica se o arquivo existe para não dar erro se faltar a imagem
        if os.path.exists('Arauco.jpg'):
            # Logo Esquerda
            self.image('Arauco.jpg', 10, 8, 30)
            # Logo Direita
            self.image('Arauco.jpg', 255, 8, 30)

        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 10, 'Relatorio de Controle de Estoque - Arauco', 0, 1, 'C')
        self.set_font('Helvetica', 'I', 10)
        self.cell(0, 5, f'Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'C')
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')


def criar_pdf(df_dados):
    pdf = PDFReport(orientation='L', unit='mm', format='A4')
    pdf.add_page()

    # 1. Sumário
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, '1. Resumo Executivo', 0, 1, 'L')

    total_vol = df_dados['Volume_Drone_Estereo'].sum()
    total_peso = df_dados['Peso_Teorico_Ton'].sum()

    df_pinus = df_dados[(df_dados['Tipo_Madeira'] == 'Pinus') & (df_dados['Peso_Tickets_Ton'] > 0)]
    df_euca = df_dados[(df_dados['Tipo_Madeira'] == 'Eucalipto') & (df_dados['Peso_Tickets_Ton'] > 0)]

    erro_pinus = df_pinus['Erro_Percentual'].abs().mean() if not df_pinus.empty else 0
    erro_euca = df_euca['Erro_Percentual'].abs().mean() if not df_euca.empty else 0

    pdf.set_font('Helvetica', '', 10)
    pdf.cell(80, 8, f"Volume Total: {total_vol:,.0f} m3", 0, 0)
    pdf.cell(80, 8, f"Estoque Total: {total_peso:,.0f} Ton", 0, 1)

    pdf.set_text_color(34, 139, 34)
    pdf.cell(80, 8, f"Erro Medio PINUS: {erro_pinus:.2f}%", 0, 0)
    pdf.set_text_color(0, 0, 139)
    pdf.cell(80, 8, f"Erro Medio EUCALIPTO: {erro_euca:.2f}%", 0, 1)

    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    # 2. Tabela
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, '2. Detalhamento', 0, 1, 'L')

    widths = [25, 25, 25, 30, 20, 30, 30, 25, 25]
    headers = ['Data', 'Pilha', 'Tipo', 'Vol (m3)', 'Dens', 'Est.(t)', 'Real(t)', 'Erro %', 'Var %']

    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(230, 230, 230)

    for i, h in enumerate(headers):
        pdf.cell(widths[i], 8, h, 1, 0, 'C', True)
    pdf.ln()

    pdf.set_font('Helvetica', '', 9)
    for index, row in df_dados.iterrows():
        dat = row['Data'].strftime('%d/%m/%Y')
        peso_real = f"{row['Peso_Tickets_Ton']:.0f}" if row['Peso_Tickets_Ton'] > 0 else "-"
        erro_txt = f"{row['Erro_Percentual']:+.1f}%" if row['Peso_Tickets_Ton'] > 0 else "-"
        var_txt = f"{row['Var_Anterior_Pct']:.1f}%"

        data_row = [
            dat, str(row['Pilha_ID']), str(row['Tipo_Madeira']),
            f"{row['Volume_Drone_Estereo']:.0f}", f"{row['Densidade_Aplicada']:.0f}",
            f"{row['Peso_Teorico_Ton']:.0f}", peso_real, erro_txt, var_txt
        ]

        for i, datum in enumerate(data_row):
            pdf.cell(widths[i], 7, datum, 1, 0, 'C')
        pdf.ln()

    return pdf.output(dest='S').encode('latin-1', 'replace')


# ==============================================================================
# 3. FUNÇÕES DE DADOS
# ==============================================================================

def get_empty_df():
    return pd.DataFrame(columns=[
        'Data', 'Pilha_ID', 'Tipo_Madeira',
        'Volume_Drone_Estereo', 'Densidade_Aplicada', 'Fator_Teorico',
        'Peso_Teorico_Ton', 'Peso_Tickets_Ton',
        'Fator_Conversao_Real', 'Erro_Ton', 'Erro_Percentual'
    ])


def load_data():
    if os.path.exists(DB_FILE):
        try:
            df = pd.read_json(DB_FILE, orient='records')
            if df.empty or 'Data' not in df.columns:
                return get_empty_df()
            return df
        except ValueError:
            return get_empty_df()
    else:
        return get_empty_df()


def save_data(df):
    try:
        df.to_json(DB_FILE, orient='records', date_format='iso')
        return True
    except Exception as e:
        st.error(f"Erro ao salvar arquivo: {e}")
        return False


# ==============================================================================
# 4. INTERFACE
# ==============================================================================

st.set_page_config(page_title="Gestão de Pátio Arauco", layout="wide")

st.markdown("""
<style>
    .stMetric { background-color: #f9f9f9; border: 1px solid #e0e0e0; padding: 10px; border-radius: 5px; }
    .stButton button { font-weight: bold; }
    .css-1v0mbdj.etr89bj1 { margin-top: 2rem; } 
</style>
""", unsafe_allow_html=True)

if 'msg_sucesso' in st.session_state:
    st.toast(st.session_state['msg_sucesso'], icon="✅")
    del st.session_state['msg_sucesso']

st.title("🌲 Controle de Estoque: Drone vs Balança")

df = load_data()

# --- SIDEBAR ---
st.sidebar.header("Nova Medição")


def atualizar_densidade():
    mes = st.session_state.data_input.month
    madeira = st.session_state.madeira_input
    st.session_state.densidade_input = float(DENSIDADE_MENSAL[mes][madeira])


if 'densidade_input' not in st.session_state:
    st.session_state.densidade_input = 580.0

data_medicao = st.sidebar.date_input("Data", datetime.now(), key='data_input')
pilha_id = st.sidebar.text_input("ID da Pilha")

tipo_madeira = st.sidebar.selectbox(
    "Tipo de Madeira",
    ['Pinus', 'Eucalipto'],
    key='madeira_input',
    on_change=atualizar_densidade
)

st.sidebar.markdown("---")
editar_densidade = st.sidebar.checkbox("Editar Densidade Manualmente?")
densidade_final = st.sidebar.number_input(
    "Densidade (kg/m³)",
    key='densidade_input',
    step=10.0,
    disabled=not editar_densidade
)

if not editar_densidade:
    st.sidebar.info(f"Padrão Automático: {densidade_final} kg/m³")

st.sidebar.markdown("---")
vol_drone = st.sidebar.number_input("Volume Drone (m³)", min_value=0.0, step=10.0)
peso_tickets = st.sidebar.number_input("Peso Balança (Ton)", min_value=0.0, step=10.0)

if st.sidebar.button("💾 REGISTRAR MEDIÇÃO", type="primary"):
    if not pilha_id:
        st.sidebar.error("⚠️ Digite o ID da Pilha.")
    elif vol_drone <= 0:
        st.sidebar.error("⚠️ O Volume deve ser maior que zero.")
    else:
        fator_teorico = FATOR_ARRUMADO[tipo_madeira]
        peso_teorico = (vol_drone * fator_teorico * densidade_final) / 1000

        if peso_tickets > 0:
            fator_conversao_real = peso_tickets / vol_drone
            erro_ton = peso_teorico - peso_tickets
            erro_pct = (erro_ton / peso_tickets) * 100
        else:
            fator_conversao_real = 0
            erro_ton = 0
            erro_pct = 0

        nova_medicao = {
            'Data': pd.to_datetime(data_medicao),
            'Pilha_ID': pilha_id,
            'Tipo_Madeira': tipo_madeira,
            'Volume_Drone_Estereo': vol_drone,
            'Densidade_Aplicada': densidade_final,
            'Fator_Teorico': fator_teorico,
            'Peso_Teorico_Ton': round(peso_teorico, 2),
            'Peso_Tickets_Ton': peso_tickets,
            'Fator_Conversao_Real': round(fator_conversao_real, 4) if peso_tickets > 0 else 0,
            'Erro_Ton': round(erro_ton, 2),
            'Erro_Percentual': round(erro_pct, 2)
        }

        df = pd.concat([df, pd.DataFrame([nova_medicao])], ignore_index=True)

        if save_data(df):
            if 'df_selecao' in st.session_state:
                del st.session_state['df_selecao']
            st.session_state['msg_sucesso'] = f"Pilha {pilha_id} registrada com sucesso!"
            st.rerun()

# --- ÁREA PRINCIPAL ---

tab_dash, tab_manual = st.tabs(["📊 Dashboard & Relatórios", "📘 Manual Metodológico"])

# ==============================================================================
# ABA 1: DASHBOARD
# ==============================================================================
with tab_dash:
    if not df.empty:
        df['Data'] = pd.to_datetime(df['Data'])
        df = df.sort_values(by=['Pilha_ID', 'Data'])
        df['Var_Anterior_Ton'] = df.groupby('Pilha_ID')['Peso_Teorico_Ton'].diff().fillna(0)
        df['Var_Anterior_Pct'] = (df.groupby('Pilha_ID')['Peso_Teorico_Ton'].pct_change() * 100).fillna(0)

        df_display = df.sort_values(by=['Data', 'Pilha_ID'], ascending=[False, True]).copy()

        if 'Selecionar' not in df_display.columns:
            df_display.insert(0, "Selecionar", False)

        st.subheader("📑 Relatório Gerencial")

        if 'df_selecao' not in st.session_state:
            st.session_state.df_selecao = df_display

        c1, c2, c3, c4 = st.columns(4)
        if c1.button("✅ Selecionar Todos"):
            st.session_state.df_selecao['Selecionar'] = True
        if c2.button("🌲 Todos Pinus"):
            st.session_state.df_selecao['Selecionar'] = st.session_state.df_selecao['Tipo_Madeira'] == 'Pinus'
        if c3.button("🌿 Todos Eucalipto"):
            st.session_state.df_selecao['Selecionar'] = st.session_state.df_selecao['Tipo_Madeira'] == 'Eucalipto'
        if c4.button("❌ Limpar"):
            st.session_state.df_selecao['Selecionar'] = False

        selecionados = st.session_state.df_selecao[st.session_state.df_selecao['Selecionar'] == True]

        if not selecionados.empty:
            k1, k2, k3 = st.columns(3)
            vol_total = selecionados['Volume_Drone_Estereo'].sum()
            peso_total = selecionados['Peso_Teorico_Ton'].sum()

            com_ticket = selecionados[selecionados['Peso_Tickets_Ton'] > 0]
            erro_medio = com_ticket['Erro_Percentual'].abs().mean() if not com_ticket.empty else 0

            k1.metric("Volume Selecionado", f"{vol_total:,.0f} m³")
            k2.metric("Peso Estimado", f"{peso_total:,.0f} ton")
            k3.metric("Acuracidade Média", f"{erro_medio:.2f}%", delta_color="inverse")

            if USE_EXTRAS:
                style_metric_cards(border_left_color="#1E90FF")

        column_config = {
            "Selecionar": st.column_config.CheckboxColumn("Sel.", width="small"),
            "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "Volume_Drone_Estereo": st.column_config.NumberColumn("Vol(m³)", format="%.0f"),
            "Peso_Teorico_Ton": st.column_config.NumberColumn("Est(t)", format="%.0f"),
            "Peso_Tickets_Ton": st.column_config.NumberColumn("Real(t)", format="%.0f"),
            "Erro_Percentual": st.column_config.NumberColumn("Erro %", format="%.1f %%"),
            "Var_Anterior_Pct": st.column_config.NumberColumn("Var %", format="%.1f %%"),
            "Fator_Conversao_Real": st.column_config.NumberColumn("Fator Real (t/m³)", format="%.4f"),
        }

        cols_view = [
            'Selecionar', 'Data', 'Pilha_ID', 'Tipo_Madeira',
            'Volume_Drone_Estereo', 'Densidade_Aplicada',
            'Peso_Teorico_Ton', 'Peso_Tickets_Ton',
            'Erro_Percentual', 'Var_Anterior_Pct',
            'Fator_Conversao_Real'
        ]

        try:
            st_data = st.data_editor(
                st.session_state.df_selecao[cols_view],
                column_config=column_config,
                hide_index=True,
                use_container_width=True,
                height=400,
                disabled=['Data', 'Pilha_ID', 'Tipo_Madeira', 'Volume_Drone_Estereo', 'Peso_Teorico_Ton',
                          'Peso_Tickets_Ton', 'Erro_Percentual', 'Var_Anterior_Pct', 'Densidade_Aplicada',
                          'Fator_Conversao_Real']
            )
        except Exception:
            st_data = st.data_editor(st.session_state.df_selecao[cols_view])

        selecionados_final = st_data[st_data['Selecionar'] == True].copy()

        if not selecionados_final.empty:
            selecionados_final['Label'] = selecionados_final['Data'].dt.strftime('%d/%m') + " - " + selecionados_final[
                'Pilha_ID']

            df_pinus = selecionados_final[selecionados_final['Tipo_Madeira'] == 'Pinus']
            df_euca = selecionados_final[selecionados_final['Tipo_Madeira'] == 'Eucalipto']

            st.markdown("### 📊 Análise Visual")

            if not df_pinus.empty:
                st.markdown("#### 🌲 PINUS")
                fig_p = go.Figure()
                fig_p.add_trace(go.Bar(
                    x=df_pinus['Label'], y=df_pinus['Peso_Teorico_Ton'],
                    name='Drone (Est.)', marker_color='#228B22',
                    text=df_pinus['Peso_Teorico_Ton'].apply(lambda x: f'{x:.0f}'), textposition='auto'
                ))
                fig_p.add_trace(go.Bar(
                    x=df_pinus['Label'], y=df_pinus['Peso_Tickets_Ton'],
                    name='Balança (Real)', marker_color='#90EE90',
                    text=df_pinus['Peso_Tickets_Ton'].apply(lambda x: f'{x:.0f}' if x > 0 else ''), textposition='auto'
                ))
                fig_p.update_layout(barmode='group', height=250, margin=dict(t=10, b=10))
                st.plotly_chart(fig_p, use_container_width=True)

            if not df_euca.empty:
                st.markdown("#### 🌿 EUCALIPTO")
                fig_e = go.Figure()
                fig_e.add_trace(go.Bar(
                    x=df_euca['Label'], y=df_euca['Peso_Teorico_Ton'],
                    name='Drone (Est.)', marker_color='#1E90FF',
                    text=df_euca['Peso_Teorico_Ton'].apply(lambda x: f'{x:.0f}'), textposition='auto'
                ))
                fig_e.add_trace(go.Bar(
                    x=df_euca['Label'], y=df_euca['Peso_Tickets_Ton'],
                    name='Balança (Real)', marker_color='#87CEFA',
                    text=df_euca['Peso_Tickets_Ton'].apply(lambda x: f'{x:.0f}' if x > 0 else ''), textposition='auto'
                ))
                fig_e.update_layout(barmode='group', height=250, margin=dict(t=10, b=10))
                st.plotly_chart(fig_e, use_container_width=True)

        st.markdown("---")
        st.subheader("📥 Exportar Relatório")

        col_csv, col_pdf = st.columns(2)

        if not selecionados_final.empty:
            with col_csv:
                csv_data = selecionados_final.to_csv(index=False).encode('utf-8')
                st.download_button("📄 Baixar CSV (Excel)", csv_data, 'relatorio_patio.csv', 'text/csv',
                                   use_container_width=True)

            with col_pdf:
                pdf_bytes = criar_pdf(selecionados_final)
                st.download_button("🖨️ Baixar PDF (Oficial)", pdf_bytes,
                                   f'Relatorio_Arauco_{datetime.now().strftime("%Y%m%d")}.pdf', 'application/pdf',
                                   type="primary", use_container_width=True)
        else:
            st.info("Selecione itens na tabela acima para liberar o download.")
    else:
        st.info("Utilize o menu lateral para registrar a primeira medição.")

# ==============================================================================
# ABA 2: MANUAL DE EQUAÇÕES E METODOLOGIA
# ==============================================================================
with tab_manual:
    st.header("📘 Manual de Metodologia e Equações")
    st.markdown(
        "Este documento descreve as fórmulas matemáticas e parâmetros de engenharia utilizados pelo software para converter volumetria de drone em massa física.")

    # 1. CÁLCULO DE TONELAGEM (DRONE)
    st.subheader("1. Cálculo de Massa Estimada (Drone)")
    st.markdown(
        "A massa da pilha é calculada convertendo o volume estéreo (geométrico) em massa sólida, considerando os vazios e a densidade específica da madeira.")

    st.latex(r'''
    M_{ton} = \frac{V_{drone} \cdot F_{e} \cdot \rho_{mes}}{1000}
    ''')

    st.markdown(r"""
    **Onde:**
    * $M_{ton}$: Massa estimada em Toneladas.
    * $V_{drone}$: Volume medido pelo drone em metros cúbicos estéreos ($m^3$).
    * $F_{e}$: Fator de Empilhamento (Adimensional). Representa a % de madeira sólida na pilha.
    * $\rho_{mes}$: Densidade da madeira ($kg/m^3$) ajustada para o mês/clima.
    * $1000$: Fator de conversão de $kg$ para $Ton$.
    """)

    with st.expander("🔎 Por que dividimos por 1000? (Análise Dimensional)"):
        st.markdown(r"""
        A densidade é dada em $kg/m^3$. O volume em $m^3$.
        Ao multiplicar, temos:
        $$ m^3 \times \frac{kg}{m^3} = kg $$
        Como a indústria comercializa em **Toneladas**, e $1 \ Ton = 1000 \ kg$, precisamos dividir o resultado final por 1000.
        """)

    st.markdown("---")

    # 2. FATORES DE CORREÇÃO E ERRO
    st.subheader("2. Validação Cruzada (Balança vs Drone)")

    c_eq1, c_eq2 = st.columns(2)
    with c_eq1:
        st.markdown(r"**Fator de Conversão Real ($Ton/m^3$)**")
        st.latex(r'''F_{conv} = \frac{M_{balanca}}{V_{drone}}''')
        st.caption(r"Indica quantas toneladas reais existem em cada $m^3$ visualizado pelo drone.")

    with c_eq2:
        st.markdown(r"**Erro Percentual ($\%$)**")
        st.latex(r'''E_{\%} = \left( \frac{M_{drone} - M_{balanca}}{M_{balanca}} \right) \times 100''')
        st.caption("Diferença relativa entre o estimado e o real.")

    st.markdown("---")

    # 3. TABELAS DE REFERÊNCIA
    st.subheader("3. Parâmetros de Engenharia (Ponta Grossa/PR)")

    st.markdown(r"#### 📅 Tabela de Densidade Sazonal ($\rho_{mes}$)")
    st.markdown(r"Valores em $kg/m^3$ considerando a variação de umidade relativa e chuvas na região.")

    # Cria DF para exibir a tabela bonitinha
    df_densidade = pd.DataFrame.from_dict(DENSIDADE_MENSAL, orient='index')
    df_densidade.index.name = 'Mês'
    st.dataframe(df_densidade, use_container_width=True)

    st.markdown(r"#### 🧱 Fatores de Empilhamento ($F_e$)")
    col_f1, col_f2 = st.columns(2)
    col_f1.metric("Pinus (Arrumado)", f"{FATOR_ARRUMADO['Pinus']}", help="Toras mais retas, menor volume de vazios.")
    col_f2.metric("Eucalipto (Arrumado)", f"{FATOR_ARRUMADO['Eucalipto']}",
                  help="Toras mais irregulares, maior volume de vazios.")

    st.markdown("---")

    # 4. DETALHAMENTO: FATOR DE CONVERSÃO REAL (NOVO)
    st.subheader(r"4. Detalhamento: Fator de Conversão Real ($F_{conv}$)")
    st.markdown(r"""
    O **Fator de Conversão Real** é um indicador empírico obtido através de Engenharia Reversa.
    Enquanto a equação teórica tenta *prever* o peso, este fator nos diz *quanto pesou de fato* cada metro cúbico medido.

    **Como interpretá-lo:**
    * Se $F_{conv} > 0,60$ (para Pinus): Indica madeira muito úmida ou empilhamento muito compacto.
    * Se $F_{conv} < 0,45$ (para Pinus): Indica madeira muito seca ou pilha "fofa" (mal arrumada).
    """)
    st.latex(r"F_{conv} = \frac{\text{Peso Total Tickets (Ton)}}{\text{Volume Total Drone (m³)}}")

    st.markdown("---")

    # 5. REFERÊNCIAS BIBLIOGRÁFICAS (NOVO)
    st.subheader("5. Referências Bibliográficas e Normas Técnicas")
    st.markdown("""
    As metodologias de cálculo, densidade e fatores de empilhamento baseiam-se nas seguintes literaturas técnicas do setor florestal:

    1.  **EMBRAPA FLORESTAS.** *Propriedades Físicas e Mecânicas da Madeira de Pinus e Eucalipto*. Comunicado Técnico, Colombo-PR.
    2.  **ABNT NBR 11941.** *Madeira - Determinação da densidade básica*. Associação Brasileira de Normas Técnicas.
    3.  **FAO (Food and Agriculture Organization).** *Global Forest Resources Assessment*. Tabela de fatores de conversão madeira sólida/estéreo.
    4.  **UFPR (Universidade Federal do Paraná).** *Manual de Inventário Florestal - Mensuração de Pilhas de Madeira*. Departamento de Engenharia Florestal.
    5.  **COTEC (Comissão Técnica de Florestas).** *Tabelas de Sazonalidade de Umidade para a Região dos Campos Gerais*.
    6.  **WOLF, A. et al.** *Accuracy of Volume Measurement of Wood Piles Using UAV Photogrammetry*. Remote Sensing, 2018. (Base para a metodologia do Drone).
    """)''