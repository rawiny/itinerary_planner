import streamlit as st
import datetime
import requests
import folium
from streamlit_folium import st_folium

from optimiser import solve_itinerary

_ = '''
1) users input their places they want to visit one by one. And users can mark if this place is a hotel they want to stay. (Users can input more than 1 hotel as the app can help users to select the hotels that suit users' need.) If this place is not a hotel, can input the time they want to spend here.
1.1) all the places users add will be shown on the map. (If possible, use one sign for attractions and another one for hotels.)
2) there are at least two ways for users to input the places: map and search in a text box and etc. (if you have a better idea, I want to hear from you.)
3) users input the start and end dates for the trip from a calendar.
4) users can choose the style they want to travel throughout the trip from a slide bar (To adjust the weights in the objective functions between shortest distance and deviation of time they travel each day).
5) users can choose the maximum number of hours they want to travel each day. And they can choose if this number is flexible or not.
6) after users input all the hotels and attractions (these places will be shown on the map), users click a button to send their inputs to the web app, and then the app will return the results by showing the routes on the map and create an itinerary (as a table?).
'''
st.set_page_config(page_title="Travel Itinerary Optimizer", layout="wide")
st.title("Travel Itinerary Optimizer")
st.markdown("""
This app helps you plan an optimized travel itinerary based on your preferences.
You can input places you want to visit, select hotels, set your trip duration, and specify your travel style and daily limits. The app will generate multiple itinerary options for you to choose from.
""")

@st.cache_data
def get_route_geometry( start_coords: dict, end_coords: dict, travel_mode = "drive") -> dict:
    api_key = st.secrets["GEOAPIFY_API_KEY"]

    start_point = f"{start_coords['lat']},{start_coords['lon']}"
    end_point = f"{end_coords['lat']},{end_coords['lon']}"
    
    url = (f"https://api.geoapify.com/v1/routing?"
           f"waypoints={start_point}|{end_point}"
           f"&mode={travel_mode}&apiKey={api_key}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for HTTP errors
        data = response.json()
        
        # read route geometry from response json
        if 'features' in data and len(data['features']) > 0:
            route_geometry = data['features'][0]['geometry']
            return route_geometry
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to get route geometry: {e}")
        return {}

with st.sidebar:
    st.header("Input Your Trip Details")

    # 1) Input places
    st.subheader("Add Places to Visit")
    place_name = st.text_input("Place Name")
    is_hotel = st.checkbox("Is this a hotel?")
    visit_duration = 0
    if not is_hotel:
        visit_duration = st.number_input("Visit Duration (hours)", min_value=1, max_value=12, value=2)

    if 'places' not in st.session_state:
        st.session_state.places = []

    if st.button("Add Place"):
        if place_name:
            # Call geocoding API to get latitude and longitude
            api_key = st.secrets["GEOAPIFY_API_KEY"]
            response = requests.get(f"https://api.geoapify.com/v1/geocode/search?text={place_name}&apiKey={api_key}")
            if response.status_code == 200:
                location = response.json()['features'][0]['geometry']['coordinates']
                lat = location[1]
                lon = location[0]
            else:
                st.error("Error fetching location data.")
                lat = 0
                lon = 0

            st.session_state.places.append({
                'name': place_name,
                'is_hotel': is_hotel,
                'duration': visit_duration,
                # read latitude from geocoding API
                'lat': lat,
                'lon': lon
            })
            #st.write(f"Added place: {place_name}, Hotel: {is_hotel}, Duration: {visit_duration} hours, Lat: {lat}, Lon: {lon}")
            st.success(f"Added {place_name}.")

    # Display added places
    if st.session_state.places:
        st.subheader("Places Added:")
        for idx, place in enumerate(st.session_state.places):
            if place["is_hotel"]:
                visit_text = "Hotel"
            else:
                visit_text = f'Visit for {place["duration"]} hours'
            st.write(f'{idx + 1}. {place["name"]} - {visit_text}')

    # 3) Trip duration
    st.subheader("Trip Duration")
    start_date = st.date_input("Start Date", datetime.date.today())
    end_date = st.date_input("End Date", datetime.date.today() + datetime.timedelta(days=5))
    trip_duration_days = (end_date - start_date).days + 1

    # 4) Travel style
    st.subheader("Travel Style")
    travel_style = st.slider("Balance between Shortest Distance and Balanced Time", 0, 100, 50)

    # 5) Daily travel limit
    st.subheader("Daily Travel Limit")
    max_daily_hours = st.number_input("Maximum Hours per Day", min_value=1, max_value=24, value=8)
    flexible_hours = st.checkbox("Flexible Daily Hours")
    is_daily_limit_flexible = flexible_hours
    objective_weights = {
        'distance_weight': travel_style / 100,
        'time_balance_weight': (100 - travel_style) / 100
    }
    if st.button("Generate Itinerary"):
        with st.spinner("Optimizing your itinerary..."):

            potential_hotels = [place for place in st.session_state.places if place['is_hotel']]
            potential_attractions = [place for place in st.session_state.places if not place['is_hotel']]

            itineraries = solve_itinerary(
                potential_hotels=potential_hotels,
                potential_attractions=potential_attractions,
                #places=st.session_state.places,
                trip_duration_days=trip_duration_days,
                max_daily_hours=max_daily_hours,
                is_daily_limit_flexible=is_daily_limit_flexible,
                objective_weights=objective_weights
            )

            # persist itineraries to session state so other parts of the app can safely read it
            st.session_state['itineraries'] = itineraries or []
        
    print("---------------------------------")
    print("User Inputs:")
    print(f"Start Date: {start_date}")
# Display the itineraries on the main page
# read safe value from session state to avoid unbound variable
itineraries = st.session_state.get('itineraries', [])

with st.expander("View Generated Itineraries"):
    if not itineraries:
        st.info("No itineraries generated yet.")
    elif 'itineraries' in st.session_state and st.session_state['itineraries']:
        itineraries = st.session_state['itineraries']
        #st.write(itineraries)
        st.success("Itinerary generated successfully!")
        # Display itineraries in tabs
        tabs = st.tabs([itinerary['title'] for itinerary in itineraries])

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
                m = folium.Map(location=[0, 0], zoom_start=2)
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
                
                st_folium(m, width=700, height=500)
                
