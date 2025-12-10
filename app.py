import streamlit as st
import datetime
import requests
import folium
from streamlit_folium import st_folium
from optimiser import solve_itinerary

# --- Page Configuration ---
st.set_page_config(page_title="Travel Itinerary Optimizer", layout="wide")

# --- Session State Initialization ---
if 'places' not in st.session_state:
    st.session_state.places = []
if 'temp_marker' not in st.session_state:
    # Stores the place currently being added/confirmed: {'lat': float, 'lon': float, 'name': str}
    st.session_state.temp_marker = None 
if 'itineraries' not in st.session_state:
    st.session_state.itineraries = []

# --- Helper Functions ---
@st.cache_data
def get_route_geometry(start_coords: dict, end_coords: dict, travel_mode="drive") -> dict:
    # (Kept your original logic)
    if "GEOAPIFY_API_KEY" not in st.secrets:
        return {}
    api_key = st.secrets["GEOAPIFY_API_KEY"]
    start_point = f"{start_coords['lat']},{start_coords['lon']}"
    end_point = f"{end_coords['lat']},{end_coords['lon']}"
    url = (f"https://api.geoapify.com/v1/routing?"
           f"waypoints={start_point}|{end_point}"
           f"&mode={travel_mode}&apiKey={api_key}")
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if 'features' in data and len(data['features']) > 0:
                return data['features'][0]['geometry']
    except Exception:
        pass
    return {}

def clear_search():
    st.session_state["search_box"] = ""

# --- Sidebar: Trip Global Settings ---
with st.sidebar:
    st.header("1. Trip Settings")
    
    st.subheader("Dates")
    start_date = st.date_input("Start Date", datetime.date.today())
    end_date = st.date_input("End Date", datetime.date.today() + datetime.timedelta(days=5))
    trip_duration_days = (end_date - start_date).days + 1
    
    st.subheader("Preferences")
    travel_style = st.slider("Optimization Balance (Distance vs. Time)", 0, 100, 50, help="0 = Shortest Distance, 100 = Balanced Time")
    max_daily_hours = st.number_input("Max Travel Hours/Day", 1, 24, 8)
    st.markdown("---")
    st.write("**How should we handle this limit?**")
    constraint_mode = st.radio(
        "Constraint Mode",
        options=["Visit All Places (Flexible Time)", "Strict Time Limit (Drop Places)"],
        index=0,
        label_visibility="collapsed"
    )

    # Logic to map user choice to boolean
    if constraint_mode == "Visit All Places (Flexible Time)":
        st.info("ℹ️ **Flexible:** We will ensure you visit **every** place, even if it exceeds your daily limit slightly.")
        flexible_hours = True
    else:
        st.warning("⚠️ **Strict:** We will **remove** places from the itinerary if they cannot fit within your daily limit.")
        flexible_hours = False

    st.divider()
    
    # Generate Button moved to Sidebar to be always visible
    st.header("3. Generate")
    if st.button("Plan My Trip!", type="primary"):
        if not st.session_state.places:
            st.error("Please add at least one place to visit.")
        else:
            with st.spinner("Running Optimization Model..."):
                objective_weights = {
                    'distance_weight': travel_style / 100,
                    'time_balance_weight': (100 - travel_style) / 100
                }
                
                potential_hotels = [p for p in st.session_state.places if p['is_hotel']]
                potential_attractions = [p for p in st.session_state.places if not p['is_hotel']]

                results = solve_itinerary(
                    potential_hotels=potential_hotels,
                    potential_attractions=potential_attractions,
                    trip_duration_days=trip_duration_days,
                    max_daily_hours=max_daily_hours,
                    is_daily_limit_flexible=flexible_hours,
                    objective_weights=objective_weights
                )
                st.session_state['itineraries'] = results or []

# --- Main Area ---

# 1. Project Header (About Section)
st.title("Travel Itinerary Optimizer")
with st.expander("ℹ️ About this Project", expanded=False):
    st.markdown("""
    **Project Overview**
    This web application utilizes advanced Applied Mathematics techniques (Mixed Integer Programming & Subtour Elimination) 
    to construct the optimal travel itinerary. It balances travel distance, time constraints, and user preferences 
    to ensure an efficient and enjoyable trip.

    **Project Team**
    * **Members:** Thitasiri Kitkhachonsak, Preeyaphat Plengchai, and Araya Adam
    * **Supervisor:** Rawin Youngnoi
    * **Department:** Mathematics and Statistics, Faculty of Science and Technology, Thammasat University
    """)

st.divider()

# 2. Place Management Section
st.header("2. Manage Locations")

col_map, col_list = st.columns([2, 1])

with col_map:
    st.subheader("Interactive Map")
    st.caption("Search for a place, or click on the map to select a location manually.")
    
    # Search Bar
    search_col1, search_col2 = st.columns([3, 1])
    with search_col1:
        search_query = st.text_input("Search Place Name", placeholder="e.g., Eiffel Tower", key="search_box")
    with search_col2:
        if st.button("Search") and search_query:
            api_key = st.secrets.get("GEOAPIFY_API_KEY", "")
            if api_key:
                try:
                    resp = requests.get(f"https://api.geoapify.com/v1/geocode/search?text={search_query}&apiKey={api_key}")
                    if resp.status_code == 200 and resp.json()['features']:
                        coords = resp.json()['features'][0]['geometry']['coordinates']
                        # Update temp marker
                        st.session_state.temp_marker = {
                            'lat': coords[1], 
                            'lon': coords[0], 
                            'name': search_query
                        }
                    else:
                        st.error("Location not found.")
                except Exception as e:
                    st.error(f"Error: {e}")
    
    # --- Map Render Logic ---
    # Center map: Priority -> Temp Marker -> Last Added Place -> Default (0,0)
    if st.session_state.temp_marker:
        center = [st.session_state.temp_marker['lat'], st.session_state.temp_marker['lon']]
        zoom = 13
    elif st.session_state.places:
        last = st.session_state.places[-1]
        center = [last['lat'], last['lon']]
        zoom = 12
    else:
        center = [13.7563, 100.5018] # Default to Bangkok or generic
        zoom = 10

    m = folium.Map(location=center, zoom_start=zoom)

    # 1. Draw Existing Confirmed Places (Blue/Green)
    for p in st.session_state.places:
        icon_color = 'green' if p['is_hotel'] else 'blue'
        icon_type = 'home' if p['is_hotel'] else 'camera'
        folium.Marker(
            [p['lat'], p['lon']], 
            popup=p['name'],
            icon=folium.Icon(color=icon_color, icon=icon_type)
        ).add_to(m)

    # 2. Draw Temp Marker (Red) - The one being added
    if st.session_state.temp_marker:
        folium.Marker(
            [st.session_state.temp_marker['lat'], st.session_state.temp_marker['lon']],
            popup="New Location (Click map to move)",
            icon=folium.Icon(color='red', icon='star')
        ).add_to(m)

    # Render Map & Capture Click
    map_output = st_folium(m, height=400, use_container_width=True)

    # Logic: If user clicks map, update temp_marker to that spot
    if map_output['last_clicked']:
        clicked_lat = map_output['last_clicked']['lat']
        clicked_lon = map_output['last_clicked']['lng']
        
        # Only update if the click is different (to avoid infinite reruns on no-change)
        # or if we want to support "picking" mode.
        st.session_state.temp_marker = {
            'lat': clicked_lat,
            'lon': clicked_lon,
            'name': "Selected Location" # Reset name if manual pick
        }
        # We need a rerun to show the red marker move immediately
        st.rerun()

    # --- Confirmation Form (Only shows if a temp marker exists) ---
    if st.session_state.temp_marker:
        st.info("👇 Confirm details for the Red Marker above")
        with st.form("confirm_place_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                final_name = st.text_input("Name", value=st.session_state.temp_marker['name'])
            with c2:
                is_hotel = st.checkbox("Is this a Hotel?")
            with c3:
                duration = st.number_input("Duration (hrs)", min_value=1, value=2, disabled=is_hotel)
            
            if st.form_submit_button("Confirm & Add Place", on_click=clear_search):
                st.session_state.places.append({
                    'name': final_name,
                    'is_hotel': is_hotel,
                    'duration': duration if not is_hotel else 0,
                    'lat': st.session_state.temp_marker['lat'],
                    'lon': st.session_state.temp_marker['lon']
                })
                # Clear temp marker after adding
                st.session_state.temp_marker = None
                st.rerun()

with col_list:
    st.subheader("Your List")
    with st.container(height=500, border=True):
        if not st.session_state.places:
            st.info("No places added yet.")
        else:
            for i, place in enumerate(st.session_state.places):
                with st.container(border=True):
                    c_info, c_del = st.columns([4, 1])
                    with c_info:
                        icon = "🏨" if place['is_hotel'] else "📍"
                        st.markdown(f"**{icon} {place['name']}**")
                        if not place['is_hotel']:
                            st.caption(f"Duration: {place['duration']} hrs")
                    with c_del:
                        if st.button("❌", key=f"del_{i}"):
                            st.session_state.places.pop(i)
                            st.rerun()

st.divider()

# 4. Results Section
st.header("4. Itinerary Results")

itineraries = st.session_state.get('itineraries', [])

if itineraries:
    tabs = st.tabs([it['title'] for it in itineraries])
    for idx, itinerary in enumerate(itineraries):
        with tabs[idx]:
            st.subheader(f"Itinerary Option: {itinerary['title']}")
            st.write(f"Total Estimated Distance: {itinerary['total_distance']:.2f} km")

            # Display daily plans
            for day_idx, daily_plan in enumerate(itinerary['daily_routes']):
                st.markdown(f"**Day {day_idx + 1}:**")
                if daily_plan:
                    for place in daily_plan:
                        st.write(f"- {place['name']} (Duration: {place.get('duration', 'N/A')} hours)")
                else:
                    st.write("No attractions planned.")

            # Map Visualization
            m = folium.Map(location=[itinerary['daily_routes'][0][0]['lat'], itinerary['daily_routes'][0][0]['lon']], zoom_start=11)
            # Mark the hotels on the map
            for place in itinerary['daily_routes'][0]:  # Assuming first day's plan includes the hotel
                if place.get('is_hotel'):
                    folium.Marker(
                        location=[place.get('lat', 0), place.get('lon', 0)],
                        popup=f"Hotel: {place['name']}",
                        icon=folium.Icon(color='red', icon='info-sign')
                    ).add_to(m)
                
            # select colours for routes each day. (The number of days is the length of itinerary['daily_routes'])
            colors = ['blue', 'green', 'purple', 'orange', 'darkred', 'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue']
                
            # Mark attractions and routes
            for day_idx, daily_plan in enumerate(itinerary['daily_routes']):
                for place in daily_plan:
                    folium.Marker(
                        location=[place.get('lat', 0), place.get('lon', 0)],
                        popup=f"Day {day_idx + 1}: {place['name']}",
                        icon=folium.Icon(color='blue' if not place.get('is_hotel') else 'red')
                    ).add_to(m)
                # Display route geometry on map
                #folium.PolyLine(locations=[(place.get('lat', 0), place.get('lon', 0)) for place in daily_plan], color=colors[day_idx % len(colors)]).add_to(m)
                for i in range(len(daily_plan) - 1):
                    start_place = daily_plan[i]
                    end_place = daily_plan[i + 1]
                    route_geometry = get_route_geometry(
                        start_coords={'lat': start_place.get('lat', 0), 'lon': start_place.get('lon', 0)},
                        end_coords={'lat': end_place.get('lat', 0), 'lon': end_place.get('lon', 0)},
                        travel_mode="drive"
                    )
                    if route_geometry and 'coordinates' in route_geometry:
                        locations = [(coord[1], coord[0]) for coord in route_geometry['coordinates'][0]]
                        folium.PolyLine(
                            locations=locations,
                            color=colors[day_idx % len(colors)]
                        ).add_to(m)
                
            st_folium(m, width=800, height=500, key=f"itinerary_map_{idx}")
else:
    st.info("Click 'Plan My Trip' to generate results.")