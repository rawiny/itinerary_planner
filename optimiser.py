import streamlit as st
import requests
from mip import Model, xsum, OptimizationStatus, minimize, INTEGER, BINARY, CONTINUOUS

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

    # --- 2. Data Cleaning and Preparation ---
    cleaned_places = []


    # รวมโรงแรมและสถานที่ทั้งหมด
    for p in potential_hotels + potential_attractions:
        # Ensure each place has a name before adding
        if "name" in p and p["name"]:
            cleaned_places.append({
                "name": p["name"],
                "lat": p.get("lat"),
                "lon": p.get("lon"),
                "duration": p.get("duration", 0) if not p.get("is_hotel", False) else 0,
                "is_hotel": p in potential_hotels  # ถ้ามาจาก potential_hotels ให้ True
            })
        else:
            print(f"Warning: Skipping place with missing name: {p}")


    # ถ้าไม่มีสถานที่เลย ให้ return ว่าง
    if not cleaned_places:
        print("Error: No valid places found after cleaning.")
        return []

    # list[str] ที่มีแค่ name
    hotels_name = [p["name"] for p in cleaned_places if p.get("is_hotel")]
    attractions_name = [p["name"] for p in cleaned_places if not p.get("is_hotel")]
    all_places_name = [p["name"] for p in cleaned_places]

    # Mapping จากชื่อ ไป index
    place_to_index = {p["name"]: i for i, p in enumerate(cleaned_places)}

    # สร้าง index
    hotel_indices = []
    for p in potential_hotels:
        if "name" in p and p["name"] in place_to_index:
            hotel_indices.append(place_to_index[p["name"]])
        else:
            print(f"Warning: Hotel '{p.get('name', 'Unnamed Hotel')}' not found in cleaned_places.")

    attraction_indices = []
    for p in potential_attractions:
        if "name" in p and p["name"] in place_to_index:
            attraction_indices.append(place_to_index[p["name"]])
        else:
             print(f"Warning: Attraction '{p.get('name', 'Unnamed Attraction')}' not found in cleaned_places.")

    all_places_indices = [place_to_index[p["name"]] for p in cleaned_places]


    # สร้าง list ของเวลาที่ใช้ในแต่ละสถานที่
    visiting_time = [p["duration"] for p in cleaned_places]

    # ตรวจสอบ
    print("Hotels:", hotels_name)
    print("Attractions:", attractions_name)
    print("All Places:", all_places_name)
    print("hotel_indices:", hotel_indices)
    print("attraction_indices:", attraction_indices)
    print("Duration:", visiting_time)

    print("Total places after cleaning:", len(cleaned_places))
    print("Cleaned Places:", cleaned_places)

    # cleaned_places ใน matrix
    distance_matrix, time_matrix = get_travel_matrices(cleaned_places)
    print("Distance Matrix:", distance_matrix)
    print("Time Matrix:", time_matrix)

    # ใช้ตอน debug
    print("place_to_index:", place_to_index)
    print("hotel_indices:", hotel_indices)
    print("attraction_indices:", attraction_indices)


    # --- 3. Simulate the Multi-Objective Optimization ---
    # แปลงข้อมูลเป็นรูปแบบที่ run_optimizer ใช้
    data = {
        "all_places_name": all_places_name,
        "hotel_indices": hotel_indices,
        "attraction_indices": attraction_indices,
        "visiting_time": visiting_time,
        "d": distance_matrix,
        "t": time_matrix,
        "day": trip_duration_days,
        "T_max": max_daily_hours,
        "flexible": is_daily_limit_flexible,
        "alpha": objective_weights.get("distance_weight"),
        "beta": objective_weights.get("time_balance_weight")
    }

    # เรียกฟังก์ชัน
    results = run_optimize(data)

    itineraries = []

    #Itinerary 1: "Optimized Route"
    optimized_plan = []
    for k, route in enumerate(results["daily_routes"]):
        # แปลง route จาก index → ชื่อสถานที่
        day_route = []
        if route:
            start_point = all_places_name[route[0][0]]
            day_route.append(start_point)
            for (i, j) in route:
                day_route.append(all_places_name[j])
        else:
            day_route = ["No route available"]

        # รวมข้อมูลต่อวัน
        optimized_plan.append({
            "day": k + 1,
            "route": day_route,
            "travel_time": round(results["daily_travel_time"][k], 2) if len(results["daily_travel_time"]) > k else None,
            "visit_time": round(results["daily_visit_time"][k], 2) if len(results["daily_visit_time"]) > k else None,
            "total_time": round(results["daily_total_time_spent"][k], 2) if len(results["daily_total_time_spent"]) > k else None,
            "distance": round(results["daily_distance"][k], 2) if len(results["daily_distance"]) > k else None
        })
    
    route_plan = []
    for k, route in enumerate(results["daily_routes"]):
        # a list of places from dictionary places (the same order as results["daily_routes"]["route"])
        print("Route for day", k+1, ":", route)
        # handle empty route safely
        if route:
            start_idx = route[0][0]
            start_place = next((place for place in potential_hotels + potential_attractions if place["name"] == all_places_name[start_idx]), None)
            daily_route = [start_place] if start_place is not None else []
            for destination_index in route:
                dest_idx = destination_index[1]
                dest_place = next((place for place in potential_hotels + potential_attractions if place["name"] == all_places_name[dest_idx]), None)
                if dest_place is not None:
                    daily_route.append(dest_place)
        else:
            daily_route = ["No route available"]
        route_plan.append(daily_route)

    itineraries.append({
        "title": "Optimized Route",
        "total_distance": round(results["total_distance"], 2),
        "total_time": round(sum(results["daily_total_time_spent"]), 2) if "daily_total_time_spent" in results else None,
        #"daily_routes": optimized_plan
        "daily_routes": route_plan
    })

    print(itineraries)
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
    print(coords)
    print(request_body)
    print(api_url)

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
                time_row.append(cell.get('time', float('inf')) / 3600)  ## แก้เป็น hour
            distance_matrix.append(distance_row)
            time_matrix.append(time_row)
        return distance_matrix, time_matrix
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to get distance matrix: {e}")
        return [], []
"""
# Mock function for offline testing (no API call)
def get_travel_matrices(places: list[dict]) -> tuple[list[list[float]], list[list[float]]]:
    n = len(places)
    distance_matrix = [[0 if i == j else abs(i - j) * 5 for j in range(n)] for i in range(n)]  # km
    time_matrix = [[0 if i == j else abs(i - j) * 0.5 for j in range(n)] for i in range(n)]    # hr
    print("⚙️ Mocked distance and time matrices generated.")
    return distance_matrix, time_matrix
"""

def run_optimize(data):
    all_places_name = data['all_places_name']
    hotel_indices = set(data['hotel_indices'])
    attraction_indices = set(data['attraction_indices'])
    visiting_time = data['visiting_time']
    d = data['d']
    t = data['t']
    day = data['day']
    T_max = data['T_max']
    flexible = data['flexible']
    alpha = data['alpha'] or 0.5
    beta = data['beta'] or 0.5

    n = len(all_places_name)
    N = set(range(n))
    H = hotel_indices
    A = attraction_indices
    K = set(range(day))

    model = Model()

    #Decision variable
    x = [[[model.add_var(var_type=BINARY) for k in K] for j in N] for i in N]         #มีเส้นทางจากสานที่ i ไป j ในวันที่ k มีค่า = 1, ไม่มีเส้นทาง = 0
    y = [[model.add_var(var_type=BINARY) for k in K] for i in N]                      #สถานที่ i ถูกเยี่ยมชมในวันที่ k มีค่า = 1, ไม่เยี่ยมชม = 0
    u = [[model.add_var(var_type=INTEGER, lb=0, ub=n-1) for k in K] for i in N]       #Subtour - MTZ
    slack = [model.add_var(lb=0.0) for k in K]                                        #ชั่วโมงที่เกิน T_max
    Z = [model.add_var(var_type=CONTINUOUS) for k in K]                                      #ผลต่างของเวลารวมต่อวัน (T_k) กับค่าเฉลี่ยเวลารวมต่อวัน (T_avg)

    #Parameter
    T = [model.add_var(lb=0) for k in K]                                              # T_k คือ เวลารวมต่อวัน
    T_avg = model.add_var(lb=0)                                                       # T_avg คือ ค่าเฉลี่ยเวลาในเเต่ละวัน


    # 1. objevtion function : หาระยะทางสั้นสุด
    objective_dist = xsum(d[i][j] * x[i][j][k] for k in K for i in N for j in N if i != j)

    # 2. objective function : หาเวลาท่องเที่ยวที่สมดุลกันในเเต่ละวัน
    objective_time_balance = xsum(Z[k] for k in K)

    # 3. objective function : ความยืดหยุ่น
    objective_slack = xsum(slack[k] for k in K)

    # 4. penalty term : ให้สถานที่อยู่ครบมากที่สุด
    objective_penalty = xsum(1 - xsum(y[i][k] for k in K) for i in A)

    #Bound max-min ของ distances
    max_d = 0.0
    min_d = 0.0
    for i in range(n):
        row_values = [d[i][j] for j in range(n) if i != j]
        max_row = max(row_values)
        min_row = min(row_values)
        max_d += max_row
        min_d += min_row


    # -------------------------
    #Normalization
    # -------------------------

    #1. distance objective
    objective_dist_min = min_d
    objective_dist_max = max_d

    #2. time balance objective
    objective_time_balance_min = 0.0
    objective_time_balance_max = T_max * len(K)

    #3. slack objective
    objective_slack_min = 0.0
    objective_slack_max = T_max * len(K)

    #4. Penalty Term
    objective_penalty_min = 0.0
    objective_penalty_max = len(A)

    #สูตร normalization x_i scaled = x_i - min(x)/max(x) - min(x)
    normalization_dist = (objective_dist - objective_dist_min) / (objective_dist_max - objective_dist_min)
    normalization_time_balance = (objective_time_balance - objective_time_balance_min) / (objective_time_balance_max - objective_time_balance_min)
    normalization_slack = (objective_slack - objective_slack_min) / (objective_slack_max - objective_slack_min)
    normalization_penalty = (objective_penalty - objective_penalty_min) / (objective_penalty_max - objective_penalty_min)


    # -------------------------
    #objective function หลังจาก normalization
    # -------------------------


    if flexible is True:
        model.objective = minimize((alpha * normalization_dist) +
                                  (beta * normalization_time_balance) +
                                  (normalization_slack))
    else:
        model.objective = minimize((alpha * normalization_dist) +
                                  (beta * normalization_time_balance)
                                  + (normalization_penalty))

    # -------------------------
    #Constraints
    # -------------------------

    # (2) เข้าสถานที่ j เพียง 1 ครั้ง ตลอดทั้งทริป
    for j in A:
        if flexible is True:
            model += xsum(x[i][j][k] for i in N if i != j for k in K) == 1
        else:
            model += xsum(x[i][j][k] for i in N if i != j for k in K) >= 0
            model += xsum(x[i][j][k] for i in N if i != j for k in K) <= 1


    # (3) ออกจากสถานที่ j เพียง 1 ครั้ง ตลอดทั้งทริป
    for i in A:
        if flexible is True:
            model += xsum(x[i][j][k] for j in N if j != i for k in K) == 1
        else:
            model += xsum(x[i][j][k] for j in N if j != i for k in K) >= 0
            model += xsum(x[i][j][k] for j in N if j != i for k in K) <= 1

    # (4) แต่ละวันจะต้องเดินทางออกจากโรงแรม 1 ครั้ง
    for k in K:
        model += xsum(x[q][j][k] for q in H for j in A if j != q) == 1

    # (5) แต่ละวันจะต้องกลับมาที่โรงแรม 1 ครั้ง
    for k in K:
        model += xsum(x[i][q][k] for q in H for i in A if i != q) == 1

    # (6) การเข้าและออกสถานที่จะเกิดขึ้นในวันเดียวกัน
    for k in K:
        for i in A:
            model += xsum(x[i][j][k] for j in N if j != i) == y[i][k]
            model += xsum(x[j][i][k] for j in N if j != i) == y[i][k]

    # (7) สมการป้องกัน subtour MTZ (VRP not CVRP yet) #เเก#
    for k in K:
        for i in A:
            for j in A:
                if i != j :
                    model.add_constr(u[i][k] - u[j][k] + n * x[i][j][k] <= n - 1)

    # (8) เริ่มต้นที่โรงแรมเป็นลำดับแรก #เเก้#
    #u[0][k] = model.add_var(lb=0, ub=0)
    for k in K:
      for q in H:
        model += u[q][k] == 0

    # (9) ค่าของ u_ik ต้องมีค่าระหว่าง 1 ถึง n #เเก่#
    for i in A:
        for k in K:
                model.add_constr(u[i][k] >= y[i][k])
                model.add_constr(u[i][k] <= (n-1)*(y[i][k]))    #(n-1) * y[i][k]

    # (10) เวลาที่ใช้ในการท่องเที่ยวแต่ละวันไม่เกินเวลาที่ผู้ใช้กำหนด จำนวนชั่วโมงที่เที่ยวได้มากที่สุด
    for k in K:
        travel_term = xsum(t[i][j]*x[i][j][k] for i in N for j in N if i != j)
        visit_term = xsum(visiting_time[j]*xsum(x[i][j][k] for i in N if i != j) for j in N)   #ไม่เอา j!=0

        if flexible is True:
            model += travel_term + visit_term <= T_max + slack[k]
        else:
            model += travel_term + visit_term <= T_max

    # (11) คำนวณเวลาที่ใช้ในการท่องเที่ยวในแต่ละวัน
    for k in K:
        # travel_time_k: เวลาเดินทางรวมในวัน k
        travel_time_k = xsum(t[i][j] * x[i][j][k]
                            for i in N for j in N if i != j)
        # visit_time_k: เวลาเยี่ยมชมรวมในวัน k  (ใช้ y[j][k] เพื่อบอกว่าไปเยือน j ในวัน _k หรือไม่)
        visit_time_k = xsum(visiting_time[j] * y[j][k] for j in N)
        # นิยาม T[k]
        model += T[k] == travel_time_k + visit_time_k

    # (12) เวลารวมเฉลี่ยในแต่ละวันที่ใช้ในการท่องเที่ยว
    model += T_avg == xsum(T[k] for k in K) / len(K)

    # (13) ความแตกต่างของเวลา
    for k in K:
        model += Z[k] >= T[k] - T_avg
        model += Z[k] >= T_avg - T[k]

    # (14), (15) คือขอบเขต x,y

    # (16) กำหนดให้จุดเริ่มต้นในวันที่ k กับจุดสิ้นสุดในวันที่ k - 1 เป็นแรงแรม q (โรงแรมเดียวกัน)
    for k in range(1, len(K)):
        for q in H:
              model += xsum(x[q][j][k] for j in A) == xsum(x[i][q][k-1] for i in A)

    # (17) กำหนดให้ในวันแรกไม่มีการเปลี่ยนโรงแรม คือ โรงแรมที่ถูกใช้ในวันที่ 1 ต้องถูกใช้ในวันที่ 2 ด้วย
    for q in H:
        model += (xsum(x[q][j][0] for j in A)) - (xsum(x[i][q][0] for i in A)) == 0

    # (18) กำหนดให้ไม่มีการเดินทางระหว่างโรงแรมกับโรงแรม
    for k in K:
        for q in H:
            for r in H:
                if q != r:
                    model.add_constr(x[q][r][k] == 0)

    # -------------------------
    #Optimizer
    # -------------------------

    results = {
        "total_distance": 0,
        "objective_value": None,
        "daily_routes": [],        # [(from_place, to_place), ...] ต่อวัน
        "daily_travel_time": [],   # travel time ต่อวัน
        "daily_visit_time": [],    # visit time ต่อวัน
        "daily_total_time_spent": [],    # total time ต่อวัน
        "daily_distance": [],      # distance ต่อวัน
        "total_slack": None,
        "penalty_value": None
    }

    status = model.optimize()
    if status == model.status.OPTIMAL or status == model.status.FEASIBLE:

        results["objective_value"] = model.objective_value
        total_dist = 0

        print("\n∘₊✧─────✧₊∘ ผลลัพธ์ของโปรแกรมวางแผนเส้นทาง ∘₊✧─────✧₊∘\n")
        print(f"objective value: {model.objective_value:.2f}\n")

        #slack & penalty
        if flexible == True:
            total_slack = sum(slack[k].x for k in K if slack[k].x is not None)
            results["total_slack"] = total_slack
            if total_slack > 0.00:
                print("\nไม่สามารถจัดเส้นทางภายใต้เวลาที่ผู้ใช้กำหนดได้")
                print("โปรเเกรมจะทำการขยายเวลาท่องเที่ยวต่อวัน เพื่อให้ครอบคลุมการท่องเที่ยวทั้งหมด\n")
        else:
            penalty_value = sum((1 - sum(y[i][k].x for k in K if y[i][k].x is not None)) for i in A)
            results["penalty_value"] = penalty_value
            if penalty_value > 0.00:
                print("\nเนื่องจากผู้ใช้งานไม่ได้ต้องการความยืดหยุ่นในแผนการท่องเที่ยว")
                print("จึงอาจจะทำการตัดสถานที่ท่องเที่ยวออกบางแห่ง เพื่อให้ครอบคลุมการท่องเที่ยวทั้งหมด\n")

        #แสดงเส้นทาง
        for k in K:
            day_dist = sum(d[i][j] * x[i][j][k].x for i in N for j in N if x[i][j][k].x is not None)
            total_dist += day_dist
            total_travel_time = sum(t[i][j]*x[i][j][k].x for i in N for j in N if i!=j and x[i][j][k].x is not None)
            total_visit_time = sum(visiting_time[j]*sum(x[i][j][k].x for i in N if i!=j and x[i][j][k].x is not None) for j in N if j not in H)
            total_time_spent = total_travel_time + total_visit_time
            day_dist = sum(d[i][j] * x[i][j][k].x for i in N for j in N if x[i][j][k].x is not None)

            print(f"Route for day {k+1}:")
            route = []

            # หาโรงแรมเริ่มต้นของวัน k
            start_hotel = None
            for q in H:
                for j in N:
                    if j != q and x[q][j][k].x is not None and x[q][j][k].x > 0.5:
                        start_hotel = q
                        break
                if start_hotel is not None:
                    break

            if start_hotel is None:
                print("  No route found for this day. (no outgoing arc from any hotel)")
                results["daily_routes"].append([])
                results["daily_travel_time"].append(0)
                results["daily_visit_time"].append(0)
                results["daily_total_time_spent"].append(0)
                results["daily_distance"].append(0)
                continue

            current = start_hotel
            visited = set()
            while True:
                found = False
                for j in N:
                    if j != current and x[current][j][k].x is not None and x[current][j][k].x > 0.5:
                        route.append((current, j))
                        if j in H and j == start_hotel:
                            found = False
                            break
                        visited.add(current)
                        current = j
                        found = True
                        break
                if not found:
                    break

            results["daily_routes"].append(route)

            for i, j in route:
                print(f"  From {all_places_name[i]} to {all_places_name[j]}")
            # แสดงเวลาในแต่ละวัน
            print(f"  Travel time: {total_travel_time:.1f} hr, Visit time: {total_visit_time:.1f} hr, Total time: {total_time_spent:.1f} hr")
            # แสดงระยะทางในแต่ละวัน
            print(f"  ระยะทางรวมวันที่ {k+1}: {day_dist:.2f} km\n")

            results["daily_travel_time"].append(total_travel_time)
            results["daily_visit_time"].append(total_visit_time)
            results["daily_total_time_spent"].append(total_time_spent)
            results["daily_distance"].append(day_dist)

        results["total_distance"] = total_dist
        print(f"ระยะทางรวมทั้งหมด: {total_dist:.2f} km\n")

    else:
        print("\nNo feasible solution found or solve failed\n")

    return results

# --- Sample input for testing solve_itinerary() ---
'''
potential_hotels = [
    {"name": "Bangkok Hotel", "lat": 13.7563, "lon": 100.5018},
    {"name": "Second Hotel", "lat": 14.7563, "lon": 100.5018}
    ]
potential_attractions = [
    {"name": "Temple of Dawn", "lat": 13.7436, "lon": 100.4889, "duration": 1},
    {"name": "Grand Palace", "lat": 13.7500, "lon": 100.4913, "duration": 2},
    {"name": "Chatuchak Market", "lat": 13.7996, "lon": 100.5500, "duration": 3},
    ]
trip_duration_days = 1
max_daily_hours = 10
is_daily_limit_flexible = True
objective_weights = {
    "distance_weight": 0.7,
    "time_balance_weight": 0.3
}

# เรียกฟังก์ชันทดสอบ
itineraries = solve_itinerary(
    potential_hotels=potential_hotels,
    potential_attractions=potential_attractions,
    trip_duration_days=trip_duration_days,
    max_daily_hours=max_daily_hours,
    is_daily_limit_flexible=is_daily_limit_flexible,
    objective_weights=objective_weights
)

# ดูผลลัพธ์
print("\n=== TEST RESULT ===")
for itinerary in itineraries:
    print(itinerary)
'''