import sys
import types
import networkx as nx 

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
    # with col_img1:
    #     if "IMG1" in st.secrets:
    #         img_1 = st.secrets["IMG1"]
    #         st.markdown(f'<img src="data:image/png;base64,{img_1}" width="100">', unsafe_allow_html=True)
            
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
        h1, h2, h3, h4, p, span, label { color: #FFFFFF !important; }
        .stDataFrame, [data-testid="stDataFrame"] {
            background-color: #FFFFFF !important;
        }
        </style>
        """, unsafe_allow_html=True)

    # --- DATA LOADING ---
    @st.cache_data
    def load_data():
        df = pd.read_csv('data/idx_network.csv') 
        
        # Load Subsidiary & Shares Data 
        try:
            df_subs = pd.read_csv('data/idx_subsidiary.csv')
        except FileNotFoundError:
            df_subs = pd.DataFrame(columns=['Emiten_Code', 'Name', 'Type', 'Values', 'Percentage']) # Empty fallback
            
        try:
            df_shares = pd.read_csv('data/idx_shares.csv')
        except FileNotFoundError:
            df_shares = pd.DataFrame(columns=['Emiten_Code', 'Name', 'Type', 'Values', 'Percentage']) # Empty fallback

        # Cleaning Network Data
        string_cols = ['Source', 'Target', 'Emiten', 'Position', 'Company']
        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
        
        if 'Company' not in df.columns:
            df['Company'] = df['Target']

        # Cleaning Detail Data 
        if 'Name' in df_subs.columns:
            df_subs['Name'] = df_subs['Name'].astype(str).str.strip()
        if 'Name' in df_shares.columns:
            df_shares['Name'] = df_shares['Name'].astype(str).str.strip()
            
        df['Emiten_Label'] = df['Emiten'] + " - " + df['Company']

        df = df.dropna(subset=['Source', 'Target'])
        return df, df_subs, df_shares

    raw_df, raw_subs, raw_shares = load_data()

    # --- PREPARE META DATA ---
    unique_emitens_df = raw_df[['Emiten', 'Company', 'Emiten_Label']].drop_duplicates().sort_values('Emiten')
    emiten_label_list = unique_emitens_df['Emiten_Label'].tolist()
    label_to_ticker = pd.Series(unique_emitens_df.Emiten.values, index=unique_emitens_df.Emiten_Label).to_dict()

    name_list = sorted(raw_df['Source'].unique())
    companies_set = set(raw_df['Target'].unique())
    
    if 'Position' in raw_df.columns:
        subsidiary_set = set(raw_df[raw_df['Position'].str.upper() == 'SUBSIDIARY']['Source'].unique())
        shareholder_set = set(raw_df[raw_df['Position'].str.upper() == 'SHAREHOLDERS']['Source'].unique())
    else:
        subsidiary_set = set()
        shareholder_set = set()

    top_25_tickers = raw_df['Emiten'].value_counts().head(25).index.tolist()

    # Emiten Colors
    emiten_list = sorted(raw_df['Emiten'].unique())
    palette = ["#FF4B4B", "#1E88E5", "#4CAF50", "#FF9800", "#9C27B0", "#00BCD4", "#795548", "#607D8B", "#E91E63", "#3F51B5"]
    emiten_color_map = {emiten: palette[i % len(palette)] for i, emiten in enumerate(emiten_list)}

    filter_css = ""
    for emiten, color in emiten_color_map.items():
        filter_css += f"""
        span[data-baseweb="tag"][aria-label*="{emiten}"] {{
            background-color: {color} !important;
            color: white !important;
        }}
        """
    st.markdown(f"<style>{filter_css}</style>", unsafe_allow_html=True)

    node_color_registry = {}
    for _, row in raw_df.iterrows():
        color = emiten_color_map.get(row['Emiten'], "#D3D3D3")
        node_color_registry[row['Source']] = color
        node_color_registry[row['Target']] = color

    # --- SIDEBAR CONTROLS ---
    st.sidebar.header("🔍 Filter")
    
    # 1. TOGGLE SWITCH
    is_top_25_mode = st.sidebar.toggle("🔥 Mode Top 25 Emiten", value=True, help="Aktif: Hanya menampilkan 25 Emiten terbesar. Non-aktif: Menampilkan semua data.")

    # 2. CHECKBOXES FOR VISIBILITY ---
    st.sidebar.divider()
    st.sidebar.subheader("👁️ Visibility")
    show_masyarakat = st.sidebar.checkbox("Tampilkan node 'MASYARAKAT'", value=True)
    show_pengendali = st.sidebar.checkbox("Tampilkan node 'PENGENDALI SAHAM'", value=True)
    
    st.sidebar.divider()
    if st.sidebar.button("🔄 Reset Dashboard"):
        st.rerun()

    # 3. FILTERS
    search_query = st.sidebar.text_input("Cari Nama / Jabatan / Emiten:", value="").upper().strip()
    
    selected_labels = st.sidebar.multiselect(
        "Pilih Emiten & Perusahaan:", 
        options=emiten_label_list, 
        default=[]
    )
    
    selected_names = st.sidebar.multiselect("Pilih Nama (Personil):", options=name_list)

    # --- FILTERING LOGIC ---
    selected_emitens_tickers = [label_to_ticker[label] for label in selected_labels]

    if is_top_25_mode:
        f_graph = raw_df[raw_df['Emiten'].isin(top_25_tickers)].copy()
        scope_label = "Top 25 Emiten"
    else:
        f_graph = raw_df.copy()
        scope_label = "All Networks"

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

    # CHECKBOX VISIBILITY LOGIC
    if not show_masyarakat:
        f_graph = f_graph[~(f_graph['Source'].str.upper().str.contains('MASYARAKAT', na=False)) & ~(f_graph['Target'].str.upper().str.contains('MASYARAKAT', na=False))]
    if not show_pengendali:
        f_graph = f_graph[~(f_graph['Source'].str.upper().str.contains('PENGENDALI SAHAM', na=False)) & ~(f_graph['Target'].str.upper().str.contains('PENGENDALI SAHAM', na=False))]

    # --- LAYOUT ---
    st.title("🛡️ Analisis Jejaring Emiten (IDX)")
    
    # --- VISUALIZATION SECTION ---
    clicked_node = None
    
    st.subheader(f"🕸️ Visualisasi Jaringan ({scope_label})")
    
    if len(f_graph) == 0:
        st.warning(f"⚠️ Tidak ada data yang ditemukan dalam mode '{scope_label}' dengan filter ini.")
        f_graph_viz = f_graph
    elif len(f_graph) > 2000:
        st.warning(f"⚠️ Data terlalu besar ({len(f_graph)} koneksi). Menampilkan 2000 koneksi teratas saja agar browser tidak crash.")
        f_graph_viz = f_graph.head(2000)
    else:
        f_graph_viz = f_graph

    # Extract Networkx properties for hovers and connection calculations
    G = nx.Graph()
    node_stats = {}

    def is_company_node(name):
        n = str(name).upper().strip()
        # Checks if it has prefix PT or suffix TBK/TBK.
        return n.startswith('PT ') or n.startswith('PT.') or n.startswith('PT') or n.endswith('TBK.') or n.endswith('TBK')

    if len(f_graph_viz) > 0:
        # Build graph to process unique connections
        G = nx.from_pandas_edgelist(f_graph_viz, source='Source', target='Target')
        
        # Initialize node stats dictionary
        for node in G.nodes():
            node_stats[node] = {'Total': 0, 'P2P': 0, 'P2C': 0, 'C2C': 0}
            
        # Count connections and classify them
        for u, v in G.edges():
            u_is_comp = is_company_node(u)
            v_is_comp = is_company_node(v)
            
            if not u_is_comp and not v_is_comp:
                cat = 'P2P'
            elif u_is_comp and v_is_comp:
                cat = 'C2C'
            else:
                cat = 'P2C'
                
            node_stats[u]['Total'] += 1
            node_stats[u][cat] += 1
            
            node_stats[v]['Total'] += 1
            node_stats[v][cat] += 1

    if len(f_graph_viz) > 0:
        all_nodes = pd.concat([f_graph_viz['Source'], f_graph_viz['Target']]).unique()
        nodes = []
        for node_id in all_nodes:
            is_company = node_id in companies_set
            is_searched = search_query and search_query in str(node_id).upper()
            
            if node_id in subsidiary_set:
                node_shape = "triangle"
                node_size = 5
            elif node_id in shareholder_set: 
                node_shape = "square"
                node_size = 5
            elif node_id in companies_set:
                node_shape = "diamond"
                node_size = 7
            else:
                node_shape = "dot"
                node_size = 3
                
            color = node_color_registry.get(node_id, "#D3D3D3")
            if is_searched:
                color = "#FF0000"
                
            # Formatting node hover info
            stats = node_stats.get(node_id, {'Total': 0, 'P2P': 0, 'P2C': 0, 'C2C': 0})
            hover_title = f"Total Connections: {stats['Total']}\nPerson-to-Person: {stats['P2P']}\nPerson-to-Company: {stats['P2C']}\nCompany-to-Company: {stats['C2C']}"

            nodes.append(Node(
                id=node_id, 
                label=node_id, 
                title=hover_title,
                size=node_size,
                color=color,
                shape=node_shape, 
                font={'size': 10, 'color': 'black'}
            ))

        edges = []
        for _, row in f_graph_viz.iterrows():
            edges.append(Edge(
                source=row['Source'], 
                target=row['Target'], 
                width=max(1, row['Weight'] / 5),
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
            avoidOverlap=1
        )

        clicked_node = agraph(nodes=nodes, edges=edges, config=config)
        
    # --- TABLES (STACKED) ---
    st.divider()
    
    net_cols = ['Source', 'Target', 'Emiten', 'Position', 'Company', 'Weight']
    net_cols = [c for c in net_cols if c in raw_df.columns]
    detail_cols = ['Emiten_Code', 'Name', 'Type', 'Values', 'Percentage']

    df_net_display = f_graph[net_cols]
    
    if selected_emitens_tickers:
         df_subs_display = raw_subs[raw_subs['Emiten_Code'].isin(selected_emitens_tickers)]
         df_shares_display = raw_shares[raw_shares['Emiten_Code'].isin(selected_emitens_tickers)]
    elif is_top_25_mode:
         df_subs_display = raw_subs[raw_subs['Emiten_Code'].isin(top_25_tickers)]
         df_shares_display = raw_shares[raw_shares['Emiten_Code'].isin(top_25_tickers)]
    else:
         df_subs_display = raw_subs 
         df_shares_display = raw_shares

    header_title = f"Detail ({scope_label})"
    
    if clicked_node:
        active_node = clicked_node
        header_title = f"Detail: {active_node}"
        
        df_net_display = raw_df[(raw_df['Source'] == active_node) | (raw_df['Target'] == active_node)]
        associated_ticker = None
        
        if active_node in companies_set:
            subset = raw_df[raw_df['Target'] == active_node]
            if not subset.empty:
                associated_ticker = subset['Emiten'].iloc[0]
        
        if associated_ticker:
            df_subs_display = raw_subs[raw_subs['Emiten_Code'] == associated_ticker]
            df_shares_display = raw_shares[raw_shares['Emiten_Code'] == associated_ticker]
        else:
            df_subs_display = raw_subs[raw_subs['Name'] == active_node]
            df_shares_display = raw_shares[raw_shares['Name'] == active_node]

    st.markdown(f"### {header_title}")
    
    with st.expander("1. Network Connections", expanded=True):
        st.dataframe(df_net_display[net_cols], use_container_width=True, hide_index=True)

    with st.expander("2. Subsidiary", expanded=True):
        st.dataframe(df_subs_display[detail_cols] if not df_subs_display.empty else pd.DataFrame(columns=detail_cols), use_container_width=True, hide_index=True)

    with st.expander("3. Shareholders", expanded=True):
        st.dataframe(df_shares_display[detail_cols] if not df_shares_display.empty else pd.DataFrame(columns=detail_cols), use_container_width=True, hide_index=True)


    # --- ADVANCED ANALYSIS ---
    st.divider()
    st.markdown("### 🔬 Advanced Analysis")
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("Calculate Betweenness Centrality"):
            st.session_state['show_centrality'] = not st.session_state.get('show_centrality', False)
    with col_btn2:
        if st.button("Count Connections"):
            st.session_state['show_connections'] = not st.session_state.get('show_connections', False)

    # 1. Betweenness Centrality Results (Graph + Table)
    if st.session_state.get('show_centrality', False) and len(f_graph_viz) > 0:
        st.markdown("#### 🌐 Betweenness Centrality Graph")
        centrality = nx.betweenness_centrality(G)
        centrality_df = pd.DataFrame(list(centrality.items()), columns=['Node', 'Centrality Score']).sort_values(by='Centrality Score', ascending=False)

        cent_nodes = []
        for node_id in G.nodes():
            cent_val = centrality.get(node_id, 0)
            cent_nodes.append(Node(
                id=node_id,
                label=node_id,
                title=f"Centrality: {cent_val:.4f}",
                size=5 + (cent_val * 60), 
                color="#FF4B4B" if cent_val > 0.05 else "#1E88E5",
                shape="dot",
                font={'size': 10, 'color': 'black'}
            ))

        cent_edges = [Edge(source=u, target=v, color="#D3D3D3") for u, v in G.edges()]

        cent_config = Config(width="100%", height=1000, directed=False, nodeHighlightBehavior=True, highlightColor="#F7A7A6", collapsible=False, backgroundColor="white")
        agraph(nodes=cent_nodes, edges=cent_edges, config=cent_config)

        st.markdown("#### 📑 Betweenness Centrality Table")
        st.dataframe(centrality_df, use_container_width=True, hide_index=True)

    # 2. Connections Results (Detailed breakdown of node counts)
    if st.session_state.get('show_connections', False) and len(f_graph_viz) > 0:
        st.markdown("#### 🔗 Node Connections Breakdown Table")
        
        stats_list = []
        for node, stats in node_stats.items():
            stats_list.append({
                'Node': node,
                'Total Connections': stats['Total'],
                'Person to Person': stats['P2P'],
                'Person to Company': stats['P2C'],
                'Company to Company': stats['C2C']
            })
            
        degree_df = pd.DataFrame(stats_list).sort_values(by='Total Connections', ascending=False)
        st.dataframe(degree_df, use_container_width=True, hide_index=True)