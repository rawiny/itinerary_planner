# optimizer.py
import random
import streamlit as st
import requests

def solve_itinerary(
    potential_hotels: list[dict],
    potential_attractions: list[dict],
    trip_duration_days: int,
    max_daily_hours: int,
    is_daily_limit_flexible: bool,
    objective_weights: dict
) -> list[dict]:
    """
    This is a placeholder function that simulates the behavior of the real
    optimization model. It takes all the user inputs and returns a list of
    pre-defined, sample itineraries.

    Args:
        potential_hotels (list[dict]): A list of hotel dictionaries selected by the user.
                                       Each dict contains 'name', 'lat', 'lon'.
        potential_attractions (list[dict]): A list of attraction dictionaries.
                                            Each dict contains 'name', 'lat', 'lon', 'duration'.
        trip_duration_days (int): The total number of days for the trip.
        max_daily_hours (int): The maximum number of hours to travel per day.
        is_daily_limit_flexible (bool): Whether the daily limit is a hard or soft constraint.
        must_see_attractions (list[str]): A list of attraction names that must be included.
        objective_weights (dict): A dict with weights, e.g., {'distance': 0.7, 'balance': 0.3}.

    Returns:
        list[dict]: A list of dictionaries, each representing a complete itinerary.
    """

    # --- 1. Print inputs for debugging (useful for you and your students) ---
    print("--- OPTIMIZATION MODEL CALLED ---")
    print(f"Potential Hotels: {[h.get('name') for h in potential_hotels]}")
    print(f"Number of Potential Attractions: {len(potential_attractions)}")
    print(f"Trip Duration: {trip_duration_days} days")
    print(f"Max Daily Hours: {max_daily_hours}")
    print(f"Flexible Limit: {is_daily_limit_flexible}")
    #print(f"Must-See Attractions: {must_see_attractions}")
    print(f"Objective Weights: {objective_weights}")
    print("---------------------------------")

    # --- 2. Basic Data Cleaning and Preparation ---
    # A real model would do more complex data prep. Here, we just ensure attractions have names.
    # We also simulate giving each attraction a random "score" for the optimizer to use.
    cleaned_attractions = []
    for place in potential_attractions:
        if place.get('name'):
            place['score'] = random.randint(50, 100) # Simulate a popularity score
            cleaned_attractions.append(place)

    if not cleaned_attractions:
        return []  # Return an empty list if there are no valid attractions

    # --- 3. Simulate Hotel Selection ---
    # A real model would use decision variables to select the best hotel.
    # For this placeholder, we'll just pick the first hotel from the user's list
    # and assume the user stays there for the whole trip.
    selected_hotel = potential_hotels[0] if potential_hotels else {'name': 'Default Hotel', 'lat': 0, 'lon': 0}

    # Each day starts and ends at the optimal hotel
    print(f"Selected Hotel for Stay: {selected_hotel['name']}")


    # Get travel matrices
    distance_matrix, time_matrix = get_travel_matrices([selected_hotel] + cleaned_attractions)
    print("Distance Matrix:", distance_matrix)
    print("Time Matrix:", time_matrix)
    
    # --- 4. Simulate the Multi-Objective Optimization ---
    # The real model would solve the MIP and generate a Pareto front.
    # Here, we will create a few different "hardcoded" itineraries to simulate this.
    # This allows you to test the tabbed UI that shows different options.

    itineraries = []

    # Itinerary 1: "Shortest Route" Simulation
    # We'll sort attractions by their distance from the hotel and pick the closest ones.
    def calculate_distance(p1, p2):
        return ((p1['lat'] - p2['lat'])**2 + (p1['lon'] - p2['lon'])**2)**0.5

    print(selected_hotel)
    sorted_by_distance = sorted(cleaned_attractions, key=lambda p: calculate_distance(p, selected_hotel))

    shortest_route_plan = []
    attractions_for_shortest = sorted_by_distance[:]
    for day in range(trip_duration_days):
        daily_plan = []
        daily_hours = 0
        # Take up to 2 attractions per day for this "relaxed" plan
        for _ in range(2):
            if attractions_for_shortest:
                attraction = attractions_for_shortest.pop(0)
                visit_duration = attraction.get('duration', 1)
                if daily_hours + visit_duration <= max_daily_hours:
                    daily_plan.append(attraction)
                    daily_hours += visit_duration
        # Each day starts and ends at the hotel
        daily_plan.insert(0, selected_hotel)
        daily_plan.append(selected_hotel)
        shortest_route_plan.append(daily_plan)

    itineraries.append({
        "title": "Shortest Route",
        "total_distance": random.uniform(50, 80), # Dummy value
        "daily_routes": shortest_route_plan
    })

    # Itinerary 2: "Most Balanced" Simulation
    # We'll try to put a similar number of attractions on each day.
    num_days = max(1, trip_duration_days)
    balanced_plan = [[] for _ in range(num_days)]
    attractions_for_balanced = cleaned_attractions[:]
    day_idx = 0
    while attractions_for_balanced:
        # Each day starts and ends at the hotel
        if len(balanced_plan[day_idx]) == 0:
            balanced_plan[day_idx].append(selected_hotel)
        
        # add hotel at end if it's the last attraction for the day
        if len(balanced_plan[day_idx]) > 0 and (len(balanced_plan[day_idx]) % 3 == 0 or not attractions_for_balanced):
            balanced_plan[day_idx].append(selected_hotel)
        balanced_plan[day_idx].append(attractions_for_balanced.pop(0))
        day_idx = (day_idx + 1) % num_days

    itineraries.append({
        "title": "Most Balanced Plan",
        "total_distance": random.uniform(80, 120), # Dummy value
        "daily_routes": balanced_plan
    })

    # --- 5. Return the list of generated itineraries ---
    return itineraries

# get distance and time travel matrices from Geoapify Route Matrix API
def get_travel_matrices(places: list[dict]) -> tuple[list[list[float]], list[list[float]]]:
    api_key = st.secrets["GEOAPIFY_API_KEY"]
    # Prepare the list of coordinates
    coords = [{"location": [place['lon'], place['lat']]} for place in places]
    
    # Call the Geoapify Route Matrix API
    api_url = f"https://api.geoapify.com/v1/routematrix?apiKey={api_key}"
    request_body = {
        "mode": "drive",
        "sources": coords,
        "targets": coords
    }

    try:
        response = requests.post(api_url, json=request_body)
        response.raise_for_status()  # Raise an exception for bad status codes
        resp_json = response.json()
        
        # read distance and time matrix from response json
        distance_matrix = []
        time_matrix = []
        for row in resp_json.get('sources_to_targets', []):
            distance_row = []
            time_row = []
            for cell in row:
                distance_row.append(cell.get('distance', float('inf')) / 1000)  # convert to km
                time_row.append(cell.get('time', float('inf')) / 60)  # convert to minutes
            distance_matrix.append(distance_row)
            time_matrix.append(time_row)
        return distance_matrix, time_matrix
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to get distance matrix: {e}")
        return [], []