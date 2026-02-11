import sys
import types

# --- PATCH FOR PYTHON 3.13 ON STREAMLIT CLOUD ---
try:
    import imghdr
except ImportError:
    imghdr = types.ModuleType("imghdr")
    imghdr.what = lambda file, h=None: None
    sys.modules["imghdr"] = imghdr
# ------------------------------------------------

import streamlit as st
import pandas as pd
from streamlit_agraph import agraph, Node, Edge, Config

# --- 1. PASSWORD PROTECTION ---
def check_password():
    """Returns True if the user had the correct password."""
    # NOTE: If you just want to run this without password, change this function to return True immediately.
    # return True 
    
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    placeholder = st.empty()
    with placeholder.container():
        st.write("## 🔒 Dashboard Login")
        # Defaulting to a simple check if secrets are not set up, for demonstration purposes
        if "APP_PASSWORD" not in st.secrets:
            st.warning("⚠️ 'APP_PASSWORD' not found in secrets.toml. allowing access for demo.")
            return True
            
        password = st.text_input("Password", type="password")
        if password:
            if password == st.secrets["APP_PASSWORD"]:
                st.session_state["password_correct"] = True
                placeholder.empty()
                st.rerun()
            else:
                st.error("😕 Password incorrect")
    return False

if check_password():   
    # --- Header Images (Placeholder logic from reference) ---
    col_img1, col_mid, col_img2 = st.columns([1, 8, 1])
    
    # Placeholder for images if secrets exist, otherwise skip to avoid errors
    with col_img1:
        if "IMG1" in st.secrets:
            img_1 = st.secrets["IMG1"]
            st.markdown(f'<img src="data:image/png;base64,{img_1}" width="100">', unsafe_allow_html=True)
            
    with col_img2:
        if "IMG2" in st.secrets:
            img_2 = st.secrets["IMG2"]
            st.markdown(f'<img src="data:image/png;base64,{img_2}" width="100">', unsafe_allow_html=True)

    # --- PAGE CONFIG & THEME ---
    st.set_page_config(
        layout="wide", 
        page_title="IDX Stocks Network Analysis",
        initial_sidebar_state="expanded"
    )

    # Force White Theme CSS
    st.markdown("""
        <style>
        .stApp { background-color: #FFFFFF; }
        [data-testid="stSidebar"] {
            background-color: #F8F9FA !important;
            border-right: 1px solid #E0E0E0;
        }
        h1, h2, h3, h4, p, span, label { color: #000000 !important; }
        .stDataFrame, [data-testid="stDataFrame"] {
            background-color: #FFFFFF !important;
        }
        </style>
        """, unsafe_allow_html=True)

    # --- DATA LOADING ---
    @st.cache_data
    def load_data():
        # Loading the provided idx_network.csv
        # Expected columns: Source, Target, Weight, Emiten, Position
        df = pd.read_csv('data/idx_network.csv')
        
        # Ensure string columns are clean
        string_cols = ['Source', 'Target', 'Emiten', 'Position', 'Company']
        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
        
        # Compatibility: Create 'Company' column if it doesn't exist
        if 'Company' not in df.columns:
            df['Company'] = df['Target']
            
        df['Emiten_Label'] = df['Emiten'] + " - " + df['Company']

        df = df.dropna(subset=['Source', 'Target'])
        return df

    raw_df = load_data()

    # --- PREPARE META DATA ---
    # Create a sorted list of unique "Ticker - Company" labels
    # We drop duplicates to get a clean list of unique companies
    unique_emitens_df = raw_df[['Emiten', 'Company', 'Emiten_Label']].drop_duplicates().sort_values('Emiten')
    emiten_label_list = unique_emitens_df['Emiten_Label'].tolist()
    
    # Map back from Label to Ticker (for filtering logic)
    label_to_ticker = pd.Series(unique_emitens_df.Emiten.values, index=unique_emitens_df.Emiten_Label).to_dict()

    name_list = sorted(raw_df['Source'].unique())
    companies_set = set(raw_df['Target'].unique())

    # Calculate Top 100 Emitens globally (using Ticker)
    top_100_tickers = raw_df['Emiten'].value_counts().head(100).index.tolist()

    # Emiten Colors
    emiten_list = sorted(raw_df['Emiten'].unique())
    palette = ["#FF4B4B", "#1E88E5", "#4CAF50", "#FF9800", "#9C27B0", "#00BCD4", "#795548", "#607D8B", "#E91E63", "#3F51B5"]
    emiten_color_map = {emiten: palette[i % len(palette)] for i, emiten in enumerate(emiten_list)}

    # Inject CSS for tags (using Ticker)
    filter_css = ""
    for emiten, color in emiten_color_map.items():
        filter_css += f"""
        span[data-baseweb="tag"][aria-label*="{emiten}"] {{
            background-color: {color} !important;
            color: white !important;
        }}
        """
    st.markdown(f"<style>{filter_css}</style>", unsafe_allow_html=True)

    # Node color registry
    node_color_registry = {}
    for _, row in raw_df.iterrows():
        color = emiten_color_map.get(row['Emiten'], "#D3D3D3")
        node_color_registry[row['Source']] = color
        node_color_registry[row['Target']] = color

    # --- SIDEBAR CONTROLS ---
    st.sidebar.header("🔍 Kontrol & Filter")
    
    # 1. TOGGLE SWITCH (Top 100 vs All)
    is_top_10_mode = st.sidebar.toggle("🔥 Mode Top 100 Emiten", value=True, help="Aktif: Hanya menampilkan 10 Emiten terbesar. Non-aktif: Menampilkan semua data.")

    st.sidebar.divider()

    if st.sidebar.button("🔄 Reset Dashboard"):
        st.rerun()

    # 2. FILTERS
    search_query = st.sidebar.text_input("Cari Nama / Jabatan / Emiten:", value="").upper().strip()
    
    # UNIFIED FILTER: Emiten & Company combined
    selected_labels = st.sidebar.multiselect(
        "Pilih Emiten & Perusahaan:", 
        options=emiten_label_list, 
        default=[]
    )
    
    selected_names = st.sidebar.multiselect("Pilih Nama (Personil):", options=name_list)

    # --- FILTERING LOGIC ---
    
    # 1. Convert selected labels back to Tickers
    selected_emitens_tickers = [label_to_ticker[label] for label in selected_labels]

    # 2. Establish Base Scope
    if is_top_10_mode:
        f_graph = raw_df[raw_df['Emiten'].isin(top_10_tickers)].copy()
        scope_label = "Top 10 Emiten"
    else:
        f_graph = raw_df.copy()
        scope_label = "All Networks"

    # 3. Apply User Filters
    if selected_emitens_tickers:
        f_graph = f_graph[f_graph['Emiten'].isin(selected_emitens_tickers)]
        
    if selected_names:
        f_graph = f_graph[f_graph['Source'].isin(selected_names)]

    if search_query:
        mask = (f_graph['Source'].str.upper().str.contains(search_query) |
                f_graph['Target'].str.upper().str.contains(search_query) |
                f_graph['Position'].str.upper().str.contains(search_query) | 
                f_graph['Emiten'].str.upper().str.contains(search_query) |
                f_graph['Company'].str.upper().str.contains(search_query))
        f_graph = f_graph[mask]

    # --- LAYOUT ---
    st.title("🛡️ Analisis Jejaring Emiten (IDX)")
    
    # --- VISUALIZATION SECTION ---
    clicked_node = None
    
    st.subheader(f"🕸️ Visualisasi Jaringan ({scope_label})")
    
    # Check for empty data
    if len(f_graph) == 0:
        st.warning(f"⚠️ Tidak ada data yang ditemukan dalam mode '{scope_label}' dengan filter ini.")
        f_graph_viz = f_graph
    
    # Safety limit
    elif len(f_graph) > 2000:
        st.warning(f"⚠️ Data terlalu besar ({len(f_graph)} koneksi). Menampilkan 2000 koneksi teratas saja agar browser tidak crash.")
        f_graph_viz = f_graph.head(2000)
    else:
        f_graph_viz = f_graph

    if len(f_graph_viz) > 0:
        # Nodes & Edges
        all_nodes = pd.concat([f_graph_viz['Source'], f_graph_viz['Target']]).unique()
        
        nodes = []
        for node_id in all_nodes:
            is_company = node_id in companies_set
            is_searched = search_query and search_query in str(node_id).upper()
            
            color = node_color_registry.get(node_id, "#D3D3D3")
            if is_searched:
                color = "#FF0000"
                
            nodes.append(Node(
                id=node_id, 
                label=node_id, 
                size=15 if is_company else 8,
                color=color,
                shape="diamond" if is_company else "dot",
                font={'size': 12, 'color': 'black'}
            ))

        edges = []
        for _, row in f_graph_viz.iterrows():
            edges.append(Edge(
                source=row['Source'], 
                target=row['Target'], 
                width=max(1, row['Weight'] / 2),
                color="#D3D3D3"
            ))

        config = Config(
            width="100%", 
            height=700, 
            directed=True,
            nodeHighlightBehavior=True, 
            highlightColor="#F7A7A6",
            collapsible=False,
            backgroundColor="white",
            link={'labelProperty': 'label', 'renderConfiguration': (True, 'blue')},
        )

        clicked_node = agraph(nodes=nodes, edges=edges, config=config)

    # --- TABLES SECTION ---
    st.divider()

    display_cols = ['Source', 'Target', 'Emiten', 'Position', 'Company', 'Weight']
    display_cols = [c for c in display_cols if c in raw_df.columns]

    if clicked_node:
        active_node = clicked_node
        if active_node in companies_set:
            st.subheader(f"🏢 Detail Perusahaan: {active_node}")
            display_df = raw_df[raw_df['Target'] == active_node]
            st.dataframe(display_df[display_cols], use_container_width=True, hide_index=True)
        else:
            st.subheader(f"👤 Profil Personil: {active_node}")
            display_df = raw_df[raw_df['Source'] == active_node]
            st.dataframe(display_df[display_cols], use_container_width=True, hide_index=True)
    else:
        # Main Table
        with st.expander(f"Lihat Data Tabel ({scope_label})", expanded=True):
            st.dataframe(f_graph[display_cols], use_container_width=True)