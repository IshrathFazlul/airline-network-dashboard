from py2neo import Graph
import networkx as nx
from bokeh.io import curdoc
from bokeh.models import (Circle, MultiLine, HoverTool, Div, Select, ColumnDataSource)
from bokeh.plotting import figure, from_networkx
from bokeh.layouts import column, row
from bokeh.transform import factor_cmap
from bokeh.palettes import Dark2_5 as node_palette
import numpy as np


# DARK THEME SETTINGS
DARK_BG = "#1e1e1e"  
DARK_CARD = "#2d2d2d"  
TEXT_LIGHT = "#ffffff"  
TEXT_MUTED = "#cccccc"  
ACCENT_COLOR = "#4ecdc4"  
NODE_COLOR = "aqua"   
EDGE_COLOR = "#9F7AEA"
#CHART_COLOR = "#FF6B6B"

# Set global dark theme
curdoc().theme = 'dark_minimal'

# DATABASE CONNECTION
graph = Graph("neo4j://127.0.0.1:7687", auth=("neo4j", "NEO-NET-DASH"), name="db-air")

# DATA QUERY FUNCTIONS
def get_airlines():
    """Get distinct airlines for dropdown"""
    query = """
    MATCH ()-[r:ROUTES_TO]->()
    WHERE r.airline_name IS NOT NULL AND r.airline_name <> ''
    RETURN DISTINCT r.airline_name AS airline
    ORDER BY airline
    """
    data = graph.run(query).data()
    return [record['airline'] for record in data] if data else ["No airlines found"]

def get_route_network(airline_name):
    """Query: Main route network for a specific airline"""
    query = """
    MATCH (origin:Airport)-[r:ROUTES_TO {airline_name: $airline_name}]->(dest:Airport)
    RETURN origin.name as origin_name, dest.name as dest_name, 
           r.airline_name as airline, r.equipment as equipment
    """
    data = graph.run(query, airline_name=airline_name).data()
    
    G = nx.DiGraph()
    for record in data:
        origin_name = record['origin_name']
        dest_name = record['dest_name']
        G.add_node(origin_name, label='Airport')
        G.add_node(dest_name, label='Airport')
        G.add_edge(origin_name, dest_name, 
                  airline_name=record['airline'], 
                  equipment=record['equipment'])
    return G

def get_airline_stats(airline_name):
    """Get statistics for the selected airline"""
    query = """
    MATCH (origin:Airport)-[r:ROUTES_TO {airline_name: $airline_name}]->(dest:Airport)
    RETURN count(r) as route_count,
           count(DISTINCT origin) as origin_airports,
           count(DISTINCT dest) as destination_airports,
           sum(CASE WHEN origin.country = dest.country THEN 1 ELSE 0 END) as domestic_routes,
           sum(CASE WHEN origin.country <> dest.country THEN 1 ELSE 0 END) as international_routes
    """
    result = graph.run(query, airline_name=airline_name).data()
    return result[0] if result else {'route_count': 0, 'origin_airports': 0, 'destination_airports': 0, 'domestic_routes': 0,'international_routes': 0}

def get_top_hubs(airline_name):
    """Get top hub airports for the selected airline"""
    query = """
    MATCH (a:Airport)-[r:ROUTES_TO {airline_name:$airline}]->()
    RETURN a.name AS airport, count(r) AS flights
    ORDER BY flights DESC LIMIT 10
    """
    return graph.run(query, airline=airline_name).data()


# GRAPH CREATION FUNCTIONS
def create_network_graph(airline_name):
    """Create the main force-directed network graph with dark theme"""
    G = get_route_network(airline_name)
    
    if len(G.nodes()) == 0:
        empty_fig = figure(
            title=f"No routes found for {airline_name}", 
            width=800, 
            height=500,
            background_fill_color=DARK_BG,
            border_fill_color=DARK_CARD
        )
        empty_fig.text(0, 0, text=["No data available"], text_color=TEXT_LIGHT, text_font_size="16px")
        return empty_fig
    
    pos = nx.spring_layout(G, k=2, iterations=100, seed=42)
    
    plot = figure(
        title=f"{airline_name} Route Network",
        tools="pan,wheel_zoom,box_zoom,reset,save",
        toolbar_location="above",
        width=600,
        height=500,
        background_fill_color=DARK_BG,
        border_fill_color=DARK_CARD,
        outline_line_color=DARK_CARD
    )
    
    plot.title.text_color = TEXT_LIGHT
    plot.title.text_font_size = "16px"
    
    plot.xaxis.axis_label_text_color = TEXT_MUTED
    plot.yaxis.axis_label_text_color = TEXT_MUTED
    plot.xaxis.major_label_text_color = TEXT_MUTED
    plot.yaxis.major_label_text_color = TEXT_MUTED
    
    graph_renderer = from_networkx(G, pos)
    
    graph_renderer.node_renderer.glyph = Circle(
        radius=0.05,
        fill_color=NODE_COLOR,  
        fill_alpha=0.8,
        line_color='lightblue',
        line_width=1
    )
    
    graph_renderer.edge_renderer.glyph = MultiLine(
        line_color=EDGE_COLOR,  
        line_alpha=0.6,
        line_width=1.5
    )
    
    # Hover tools with dark theme
    node_hover = HoverTool(
        tooltips="""
        <div style="background: #2d2d2d; padding: 5px; border-radius: 3px; color: #ffffff;">
            <span style="font-weight: bold;">Airport:</span> @index
        </div>
        """,
        renderers=[graph_renderer.node_renderer]
    )
    
    edge_hover = HoverTool(
        tooltips="""
        <div style="background: #2d2d2d; padding: 5px; border-radius: 3px; color: #ffffff;">
            <div><span style="font-weight: bold;">Airline:</span> @airline_name</div>
            <div><span style="font-weight: bold;">Equipment:</span> @equipment</div>
        </div>
        """,
        renderers=[graph_renderer.edge_renderer],
        line_policy='interp'
    )
    
    plot.add_tools(node_hover, edge_hover)
    plot.renderers.append(graph_renderer)
    plot.axis.visible = False
    plot.grid.visible = False
    
    plot.grid.grid_line_color = "#444444"
    plot.grid.grid_line_alpha = 0.3
    
    return plot

def create_hub_chart(airline_name):
    """Create a horizontal bar chart showing top hub airports"""
    hubs_data = get_top_hubs(airline_name)
    
    if not hubs_data:
        empty_fig = figure(
            title=f"No hub data for {airline_name}",
            width=800,
            height=500,
            background_fill_color=DARK_BG,
            border_fill_color=DARK_CARD
        )
        empty_fig.text(0, 0, text=["No data available"], text_color=TEXT_LIGHT, text_font_size="16px")
        return empty_fig
    
    # Prepare data
    airports = [hub['airport'] for hub in hubs_data]
    flights = [hub['flights'] for hub in hubs_data]
    
    # Create figure
    p = figure(
        y_range=airports,
        title=f"Top Hub Airports - {airline_name}",
        width=600,
        height=500,
        tools="pan,wheel_zoom,box_zoom,reset,save",
        toolbar_location="above",
        background_fill_color=DARK_BG,
        border_fill_color=DARK_CARD,
        outline_line_color=DARK_CARD
    )
    
    # Style the plot
    p.title.text_color = TEXT_LIGHT
    p.title.text_font_size = "16px"
    p.xaxis.axis_label = "Number of Outbound Routes"
    p.xaxis.axis_label_text_color = TEXT_MUTED
    p.yaxis.axis_label_text_color = TEXT_MUTED
    p.xaxis.major_label_text_color = TEXT_MUTED
    p.yaxis.major_label_text_color = TEXT_MUTED
    
    # Create horizontal bars
    source = ColumnDataSource(data=dict(
        airports=airports,
        flights=flights
    ))
    
    bars = p.hbar(
        y='airports', 
        right='flights', 
        height=0.6,
        source=source,
        fill_color=EDGE_COLOR,
        line_color="white",
        fill_alpha=0.8
    )
    
    # Add hover tool
    hover = HoverTool(
        tooltips="""
        <div style="background: #2d2d2d; padding: 5px; border-radius: 3px; color: #ffffff;">
            <div><span style="font-weight: bold;">Airport:</span> @airports</div>
            <div><span style="font-weight: bold;">Outbound Routes:</span> @flights</div>
        </div>
        """,
        renderers=[bars]
    )
    p.add_tools(hover)
    
    # Style grid
    p.grid.grid_line_color = "#444444"
    p.grid.grid_line_alpha = 0.3
    
    return p

def create_airline_stats(airline_name):
    """Create statistics display with dark theme as horizontal cards"""
    stats = get_airline_stats(airline_name)
    
    stats_html = f"""
    <div style="display: flex; justify-content: space-between; gap: 15px; margin-bottom: 20px;">
        <!-- Total Routes Card -->
        <div style="flex: 1; 
                    padding: 20px; 
                    background: {DARK_CARD};
                    border-radius: 8px;
                    color: {TEXT_LIGHT};
                    text-align: center;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    border-top: 4px solid {ACCENT_COLOR};">
            <h3 style="color: {ACCENT_COLOR}; margin-top: 0; margin-bottom: 10px;">
                Total Routes
            </h3>
            <p style="font-size: 24px; font-weight: bold; color: {EDGE_COLOR}; margin: 0;">
                {stats['route_count']}
            </p>
        </div>
        
        <!-- Origin Airports Card -->
        <div style="flex: 1; 
                    padding: 20px; 
                    background: {DARK_CARD};
                    border-radius: 8px;
                    color: {TEXT_LIGHT};
                    text-align: center;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    border-top: 4px solid {ACCENT_COLOR};">
            <h3 style="color: {ACCENT_COLOR}; margin-top: 0; margin-bottom: 10px;">
                Origin Airports
            </h3>
            <p style="font-size: 24px; font-weight: bold; color: {EDGE_COLOR}; margin: 0;">
                {stats['origin_airports']}
            </p>
        </div>
        
        <!-- Destination Airports Card -->
        <div style="flex: 1; 
                    padding: 20px; 
                    background: {DARK_CARD};
                    border-radius: 8px;
                    color: {TEXT_LIGHT};
                    text-align: center;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    border-top: 4px solid {ACCENT_COLOR};">
            <h3 style="color: {ACCENT_COLOR}; margin-top: 0; margin-bottom: 10px;">
                Destination Airports
            </h3>
            <p style="font-size: 24px; font-weight: bold; color: {EDGE_COLOR}; margin: 0;">
                {stats['destination_airports']}
            </p>
        </div>
        
        <!-- Domestic Routes Card -->
        <div style="flex: 1; 
                    padding: 20px; 
                    background: {DARK_CARD};
                    border-radius: 8px;
                    color: {TEXT_LIGHT};
                    text-align: center;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    border-top: 4px solid {ACCENT_COLOR};">
            <h3 style="color: {ACCENT_COLOR}; margin-top: 0; margin-bottom: 10px;">
                Domestic Routes
            </h3>
            <p style="font-size: 24px; font-weight: bold; color: {EDGE_COLOR}; margin: 0;">
                {stats['domestic_routes']}
            </p>
        </div>
        
        <!-- International Routes Card -->
        <div style="flex: 1; 
                    padding: 20px; 
                    background: {DARK_CARD};
                    border-radius: 8px;
                    color: {TEXT_LIGHT};
                    text-align: center;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    border-top: 4px solid {ACCENT_COLOR};">
            <h3 style="color: {ACCENT_COLOR}; margin-top: 0; margin-bottom: 10px;">
                International Routes
            </h3>
            <p style="font-size: 24px; font-weight: bold; color: {EDGE_COLOR}; margin: 0;">
                {stats['international_routes']}
            </p>
        </div>
    </div>
    """
    
    return Div(text=stats_html, width=1600, height=80)
# CREATE DASHBOARD
def create_dashboard():
    """Create the main dashboard with dark theme"""
    
    # Get all airlines
    airlines = get_airlines()
    print(f"Found {len(airlines)} airlines")
    
    if not airlines:
        return Div(text=f"<h1 style='color: {TEXT_LIGHT};'>No airlines found in database</h1>", width=800, height=600)
    
    initial_airline = airlines[0]
    
    # Create initial components
    network_graph = create_network_graph(initial_airline)
    hub_chart = create_hub_chart(initial_airline)
    stats_div = create_airline_stats(initial_airline)
    
    # Create dropdown with dark theme styling
    airline_select = Select(
        title="Select Airline:", 
        value=initial_airline, 
        options=airlines, 
        width=590,
        height=40
    )
    
    # Style the dropdown for dark theme
    airline_select.styles = {
        'color': TEXT_LIGHT,
        'background-color': DARK_CARD,
        'border-color': '#555'
    }
    
    # Create title with dark theme
    title_div = Div(
        text=f"""
        <div style="text-align: center; 
                    background: linear-gradient(135deg, #2d2d2d 0%, #1e1e1e 100%);
                    padding: 25px; 
                    border-bottom: 2px solid {ACCENT_COLOR};
                    color: {TEXT_LIGHT};">
            <h1 style="margin: 0; font-size: 2.5em; color: {ACCENT_COLOR};"> ✈️Airline Network Dashboard</h1>
        </div>
        """, 
        width=3200, 
        height=100
    )
    
    # Layout with dark background
    controls = row([airline_select], sizing_mode="fixed")
    
    # Top row: Network graph and hub chart
    top_row = row([network_graph, hub_chart], sizing_mode="stretch_both")
    
    # Bottom row: Statistics
    bottom_row = row([stats_div], sizing_mode="stretch_both")
    
    # Main dashboard container with dark background
    dashboard = column(
        title_div,
        controls,
        top_row,
        bottom_row,
        sizing_mode="stretch_both",
        spacing=20,
        background=DARK_BG
    )
    
    # Update function
    def update_dashboard(attr, old, new):
        selected_airline = airline_select.value
        new_network = create_network_graph(selected_airline)
        new_hub_chart = create_hub_chart(selected_airline)
        new_stats = create_airline_stats(selected_airline)
        
        top_row.children[0] = new_network
        top_row.children[1] = new_hub_chart
        bottom_row.children[0] = new_stats
    
    airline_select.on_change('value', update_dashboard)
    
    return dashboard

# SET UP BOKEH DOCUMENT
try:
    # Set global dark background
    curdoc().background = DARK_BG
    dashboard = create_dashboard()
    curdoc().add_root(dashboard)
    curdoc().title = "Airline Network Dashboard - Enhanced with Hub Analysis"
    print("Enhanced dashboard with hub analysis created successfully!")
    
except Exception as e:
    error_div = Div(text=f"<h1 style='color: {TEXT_LIGHT};'>Error</h1><pre style='color: {TEXT_LIGHT};'>{str(e)}</pre>", 
                   width=800, height=600)
    curdoc().add_root(error_div)
    print(f"Error creating dashboard: {e}")