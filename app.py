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

    # --- 2. DATA LOADING ---
    @st.cache_data
    def load_data():
        # Loading the provided idx_network.csv
        # Expected columns: Source, Target, Weight, Emiten, Position
        network_df = pd.read_csv('data/idx_network.csv')
        
        # Cleaning whitespace
        string_cols = ['Source', 'Target', 'Emiten', 'Position']
        for col in string_cols:
            if col in network_df.columns:
                network_df[col] = network_df[col].astype(str).str.strip()
        
        network_df = network_df.dropna(subset=['Source', 'Target'])
        return network_df

    try:
        raw_df = load_data()
    except FileNotFoundError:
        st.error("❌ File 'idx_network.csv' not found. Please upload it to the directory.")
        st.stop()

    # --- 3. PREPARE FILTER LISTS ---
    # Adapting logic: "Bank" -> "Emiten" (Ticker), "Target" -> Company Name
    emiten_list = sorted(raw_df['Emiten'].unique())
    company_list = sorted(raw_df['Target'].unique()) # Companies acts like "Banks" in graph shape
    name_list = sorted(raw_df['Source'].unique())

    # Color map for Emitens (Cycling through a palette)
    palette = ["#FF4B4B", "#1E88E5", "#4CAF50", "#FF9800", "#9C27B0", "#00BCD4", "#795548", "#607D8B", "#E91E63", "#3F51B5"]
    emiten_color_map = {emiten: palette[i % len(palette)] for i, emiten in enumerate(emiten_list)}

    # Injecting CSS for multiselect tags to match Emiten colors
    filter_css = ""
    for emiten, color in emiten_color_map.items():
        filter_css += f"""
        span[data-baseweb="tag"][aria-label*="{emiten}"] {{
            background-color: {color} !important;
            color: white !important;
        }}
        """
    st.markdown(f"<style>{filter_css}</style>", unsafe_allow_html=True)

    # Node color registry: Nodes inherit color from their Emiten
    node_color_registry = {}
    for _, row in raw_df.iterrows():
        color = emiten_color_map.get(row['Emiten'], "#D3D3D3")
        node_color_registry[row['Source']] = color # Person gets Emiten color
        node_color_registry[row['Target']] = color # Company gets Emiten color

    # --- 4. SIDEBAR (FILTERS) ---
    st.sidebar.header("🔍 Filter & Pencarian")

    if st.sidebar.button("🔄 Reset Dashboard"):
        for key in ["search_query", "selected_emitens", "selected_names"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    search_query = st.sidebar.text_input("Cari Nama / Jabatan / Emiten:", value="").upper().strip()
    
    # Adapted Filters
    selected_emitens = st.sidebar.multiselect("Pilih Emiten (Ticker):", options=emiten_list, default=emiten_list[:5]) # Default to first 5 to avoid clutter
    selected_names = st.sidebar.multiselect("Pilih Nama (Personil):", options=name_list)
    
    # Note: Broker filter removed as no broker data was provided in idx_network.csv

    # --- 5. FILTERING LOGIC ---
    f_graph = raw_df[raw_df['Emiten'].isin(selected_emitens)].copy()

    if selected_names:
        f_graph = f_graph[f_graph['Source'].isin(selected_names)]

    if search_query:
        mask = (f_graph['Source'].str.upper().str.contains(search_query) |
                f_graph['Target'].str.upper().str.contains(search_query) |
                f_graph['Position'].str.upper().str.contains(search_query) | 
                f_graph['Emiten'].str.upper().str.contains(search_query))
        f_graph = f_graph[mask]

    # --- 6. NETWORK PREPARATION ---
    # Limiting nodes for performance if too many are selected
    if len(f_graph) > 500:
        st.sidebar.warning(f"⚠️ Data too large ({len(f_graph)} connections). Showing top 500.")
        f_graph = f_graph.head(500)

    all_nodes = pd.concat([f_graph['Source'], f_graph['Target']]).unique()
    
    # Identify which nodes are Companies (Targets) vs People (Source)
    # In this dataset, Target columns are the Companies.
    companies_set = set(raw_df['Target'].unique())

    nodes = []
    for node_id in all_nodes:
        # Shape Logic: Company (Target) = Diamond, Person (Source) = Dot
        is_company = node_id in companies_set
        
        # Search Highlighting
        is_searched = search_query and search_query in str(node_id).upper()
        
        # Color Logic
        color = node_color_registry.get(node_id, "#D3D3D3")
        if is_searched:
            color = "#FF0000" # Highlight searched node
            
        nodes.append(Node(
            id=node_id, 
            label=node_id, 
            size=15 if is_company else 8,
            color=color,
            shape="diamond" if is_company else "dot",
            font={'size': 12, 'color': 'black'}
        ))

    edges = []
    for _, row in f_graph.iterrows():
        edges.append(Edge(
            source=row['Source'], 
            target=row['Target'], 
            # label=row['Position'], # Optional: Un-comment to show position on line
            width=max(1, row['Weight'] / 2),
            color="#D3D3D3"
        ))

    # --- 7. VISUALIZATION LAYOUT ---
    st.title("🛡️ Analisis Jejaring Emiten (IDX)")
    st.subheader("🕸️ Visualisasi Jaringan")

    config = Config(
        width="100%", 
        height=700, 
        directed=True,
        nodeHighlightBehavior=True, 
        collapsible=False,
        highlightColor="#F7A7A6",
        canvasBackgroundColor="white",
        link={'labelProperty': 'label', 'renderConfiguration': (True, 'blue')},
        physics={
            'enabled': True,
            'solver': 'forceAtlas2Based', # Often better for medium networks
            'forceAtlas2Based': {'gravitationalConstant': -50, 'springLength': 100}
        }
    )

    clicked_node = agraph(nodes=nodes, edges=edges, config=config)

    # --- 8. TABLES (Bottom Section) ---
    st.divider()

    # Logic to handle clicks
    if clicked_node:
        active_node = clicked_node
        
        # Check if clicked node is a Company (Target)
        if active_node in companies_set:
            st.subheader(f"🏢 Detail Perusahaan: {active_node}")
            # Show all people connected to this company
            display_df = raw_df[raw_df['Target'] == active_node]
            
            st.dataframe(
                display_df[['Source', 'Target', 'Emiten', 'Position', 'Weight']], 
                use_container_width=True, 
                hide_index=True
            )
            
        # Otherwise, it's a Person (Source)
        else:
            st.subheader(f"👤 Profil Personil: {active_node}")
            # Show all companies this person is connected to
            display_df = raw_df[raw_df['Source'] == active_node]
            
            st.dataframe(
                display_df[['Source', 'Target', 'Emiten', 'Position', 'Weight']], 
                use_container_width=True, 
                hide_index=True
            )
    else:
        st.info("💡 Klik node Diamond (Perusahaan) atau Dot (Personil) untuk melihat detail koneksi.")
        # Default view: Show filtered table
        with st.expander("Lihat Data Tabel Lengkap (Filtered)"):
            st.dataframe(f_graph, use_container_width=True)