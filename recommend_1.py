import json
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime
from sklearn.metrics.pairwise import cosine_similarity
from pymongo import MongoClient
from scorer import calculate_dish_score

# --------------------- CONFIG ---------------------
st.set_page_config(page_title="🍽️ Hybrid Dish Recommender", layout="wide")
st.title("🍽️ Hybrid Dish Recommender with Nutritional + Personalized Intelligence")

# --------------------- DB & FILE SETUP ---------------------
MONGO_URI = "mongodb://fitshield:fitshield123@13.235.70.79:27017/Fitshield?directConnection=true&appName=mongosh+2.4.2"
client = MongoClient(MONGO_URI)
db = client["Fitshield"]
menu_collection = db["RestaurantMenuData"]
user_collection = db["UserData"]

@st.cache_data
def load_encoded_vectors():
    df = pd.read_csv("encoded_dishes.csv")

    # Automatically drop non-numeric columns except 'dish_name'
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    feature_cols = [col for col in numeric_cols if col != "dish_name"]

    return df, feature_cols


encoded_df, feature_cols = load_encoded_vectors()
menu_data = menu_collection.find_one()
menu_items = menu_data["menu"] if menu_data else []

# Function to extract macro nutrients from a dish
def extract_nutrients(dish):
    macro_nutrients = dish["dish_variants"]["normal"]["full"]["calculate_nutrients"]["macro_nutrients"]
    return {n["name"]: n["value"] for n in macro_nutrients}

# Function to extract both maximum and minimum nutrient values from all dishes
def find_max_min_nutrients(dishes):
    max_nutrients = {}
    min_nutrients = {}

    for dish in dishes:
        nutrients = extract_nutrients(dish)
        for name, value in nutrients.items():
            if name not in max_nutrients:
                max_nutrients[name] = value
                min_nutrients[name] = value
            else:
                max_nutrients[name] = max(max_nutrients[name], value)
                min_nutrients[name] = min(min_nutrients[name], value)

    return max_nutrients, min_nutrients

# Wrapper function
def get_max_min_nutrient_values(menu_items):
    return find_max_min_nutrients(menu_items)

# Usage
max_nutrients, min_nutrients = get_max_min_nutrient_values(menu_items)

# --------------------- USER SELECTION ---------------------
user_ids = [u["_id"] for u in user_collection.find({}, {"_id": 1})]
selected_user_id = st.selectbox("Select User", user_ids)

# --------------------- Reset actions on user switch ---------------------
if "last_user" not in st.session_state:
    st.session_state.last_user = selected_user_id

if st.session_state.last_user != selected_user_id:
    st.session_state.actions = []
    st.session_state.prev_liked_dishes = []
    st.session_state.last_user = selected_user_id

# Fetch user data
user = user_collection.find_one({"_id": selected_user_id})
hunger_level = user.get("hunger_level", "Medium")

# --------------------- SESSION ACTION LOG ---------------------
if "actions" not in st.session_state:
    st.session_state.actions = []

# --------------------- INPUT: NUTRITION GOALS ---------------------
st.subheader("🔧 Nutritional Goals")
col1, col2, col3, col4, col5 = st.columns(5)
protein_goal = col1.number_input("Protein (g)", value=22.0)
carbs_goal = col2.number_input("Carbs (g)", value=22.0)
fats_goal = col3.number_input("Fats (g)", value=19.0)
fiber_goal = col4.number_input("Fibers (g)", value=7.0)
energy_goal = col5.number_input("Energy (kcal)", value=300.0)

user_live_goal = {
    "proteins": protein_goal,
    "carbs": carbs_goal,
    "fats": fats_goal,
    "fibers": fiber_goal,
    "energy": energy_goal
}

# --------------------- VARIABLES FOR PERCENTAGE DIFFERENCE AND FACTORS ---------------------
# Calculate percentage differences for nutritional goals
default_goal_protein = 1.0  # Example default values (can be adjusted based on actual goals)
default_goal_carbs = 1.0
default_goal_fats = 1.0
default_goal_fibers = 1.0

# Calculate the live goal values for nutrients (can adjust according to input or existing data)
live_goal_protein = protein_goal
live_goal_carbs = carbs_goal
live_goal_fats = fats_goal
live_goal_fibers = fiber_goal

percentage_difference_protein = round(((live_goal_protein - default_goal_protein) / default_goal_protein) * 100, 2)
percentage_difference_carbs = round(((live_goal_carbs - default_goal_carbs) / default_goal_carbs) * 100, 2)
percentage_difference_fats = round(((live_goal_fats - default_goal_fats) / default_goal_fats) * 100, 2)
percentage_difference_fibers = round(((live_goal_fibers - default_goal_fibers) / default_goal_fibers) * 100, 2)

percentage_difference = {
    "proteins": percentage_difference_protein,
    "carbs": percentage_difference_carbs,
    "fats": percentage_difference_fats,
    "fibers": percentage_difference_fibers
}

# Default factors for the scoring calculation
default_factors = {
    "protein": 1.0,
    "carbs": 1.0,
    "fats": 1.0,
    "fibers": 1.0,
    "energy": 1.0,
    "density_factor": 1.0,
    "satiety_factor": 1.0,
    "euclidean_factor": 1.0
}

# Rule-based factors for the scoring
rule_factors = {
    "protein_overrule_factor": 1.0,
    "low_carbs_overrule_factor": 1.0,
    "low_fat_overrule_factor": 1.0,
    "sugar_content_factor": 1.0,
    "sodium_content_factor": 1.0,
    "saturated_fat_factor": 1.0,
    "cholesterol_factor": 1.0,
    "caloric_density_factor": 1.0,
    "good_fats_factor": 1.0
}

# --------------------- INPUT: TIME ---------------------
input_time = st.text_input("Enter current time (HH:MM format)", "08:30")

def get_time_category(input_time):
    t = datetime.strptime(input_time, "%H:%M").time()
    if 6 <= t.hour < 10: return "Breakfast"
    elif 10 <= t.hour < 12: return "Brunch"
    elif 12 <= t.hour < 17: return "Lunch"
    elif 17 <= t.hour < 22: return "Dinner"
    elif 22 <= t.hour < 24 or 0 <= t.hour < 2: return "Midnight Snack"
    return "Snack"

# --------------------- NUTRITIONAL TRANSPARENCY ---------------------
# Display the comparison for both max and min values
st.subheader("🔍 Nutritional Transparency: Max and Min Nutritional Content in Dishes")
st.write(f"Max Protein in Restaurant Dishes: {max_nutrients['proteins']}g | Min Protein: {min_nutrients['proteins']}g")
st.write(f"Max Carbs in Restaurant Dishes: {max_nutrients['carbs']}g | Min Carbs: {min_nutrients['carbs']}g")
st.write(f"Max Fats in Restaurant Dishes: {max_nutrients['fats']}g | Min Fats: {min_nutrients['fats']}g")
st.write(f"Max Fiber in Restaurant Dishes: {max_nutrients['fibers']}g | Min Fiber: {min_nutrients['fibers']}g")

# Compare with user's live goal
# st.subheader("🥗 Your Nutritional Goals vs Restaurant's Offerings")
# st.write(f"Your Protein Goal: {protein_goal}g | Max Protein in Restaurant: {max_nutrients['proteins']}g | Min Protein: {min_nutrients['proteins']}g")
# st.write(f"Your Carbs Goal: {carbs_goal}g | Max Carbs in Restaurant: {max_nutrients['carbs']}g | Min Carbs: {min_nutrients['carbs']}g")
# st.write(f"Your Fats Goal: {fats_goal}g | Max Fats in Restaurant: {max_nutrients['fats']}g | Min Fats: {min_nutrients['fats']}g")
# st.write(f"Your Fiber Goal: {fiber_goal}g | Max Fiber in Restaurant: {max_nutrients['fibers']}g | Min Fiber: {min_nutrients['fibers']}g")

# Show any deficiencies or surpluses
if max_nutrients['proteins'] < protein_goal:
    st.warning("Restaurant's offerings may not meet your protein goal!")
if min_nutrients['proteins'] > protein_goal:
    st.warning("Restaurant's offerings may exceed your protein goal!")
if max_nutrients['carbs'] < carbs_goal:
    st.warning("Restaurant's offerings may not meet your carbs goal!")
if min_nutrients['carbs'] > carbs_goal:
    st.warning("Restaurant's offerings may exceed your carbs goal!")
if max_nutrients['fats'] < fats_goal:
    st.warning("Restaurant's offerings may not meet your fats goal!")
if min_nutrients['fats'] > fats_goal:
    st.warning("Restaurant's offerings may exceed your fats goal!")
if max_nutrients['fibers'] < fiber_goal:
    st.warning("Restaurant's offerings may not meet your fiber goal!")
if min_nutrients['fibers'] > fiber_goal:
    st.warning("Restaurant's offerings may exceed your fiber goal!")

# --------------------- INTERACTION SECTION ---------------------
st.subheader("🧪 Interact with Dishes")
dish_names = [d["dish_name"] for d in menu_items]

# Initialize liked dish tracking
if "prev_liked_dishes" not in st.session_state:
    st.session_state.prev_liked_dishes = []

liked_dishes = st.multiselect("❤️ Liked Dishes", dish_names)
searched_dish = st.text_input("🔎 Search Dish")

# ➕ Log newly liked dishes
new_likes = set(liked_dishes) - set(st.session_state.prev_liked_dishes)
for dish in new_likes:
    st.session_state.actions.append({
        "timestamp": str(datetime.now()),
        "action": "liked",
        "dish": dish,
        "user_id": selected_user_id
    })

# ❌ Remove unliked dishes from action log
removed_likes = set(st.session_state.prev_liked_dishes) - set(liked_dishes)
if removed_likes:
    st.session_state.actions = [
        act for act in st.session_state.actions
        if not (act["action"] == "liked" and act["dish"] in removed_likes and act["user_id"] == selected_user_id)
    ]

# Update previous liked state
st.session_state.prev_liked_dishes = liked_dishes

# Log searched dish if exists
if searched_dish and searched_dish in dish_names:
    st.session_state.actions.append({
        "timestamp": str(datetime.now()), "action": "searched", "dish": searched_dish, "user_id": selected_user_id
    })

# Expanded dish interaction options
for dish in dish_names:
    with st.expander(f"🍽️ {dish}"):
        col1, col2, col3, col4 = st.columns(4)
        if col1.button(f"🛒 Add to Cart - {dish}"):
            st.session_state.actions.append({
                "timestamp": str(datetime.now()), "action": "add_to_cart", "dish": dish, "user_id": selected_user_id
            })
        if col2.button(f"👁️ Viewed - {dish}"):
            st.session_state.actions.append({
                "timestamp": str(datetime.now()), "action": "viewed", "dish": dish, "user_id": selected_user_id
            })

        if col3.button(f"📥 Downloaded - {dish}"):
            st.session_state.actions.append({
                "timestamp": str(datetime.now()), "action": "download", "dish": dish, "user_id": selected_user_id
            })
            
        if col4.button(f"✅ Ordered - {dish}"):
            st.session_state.actions.append({
                "timestamp": str(datetime.now()), "action": "ordered", "dish": dish, "user_id": selected_user_id
            })

# --------------------- BUILD USER VECTOR ---------------------
def get_user_vector(actions):
    weights = {
        "liked": 1.0,
        "ordered": 0.9,
        "download": 0.7,
        "add_to_cart": 0.8,
        "searched": 0.4,
        "viewed": 0.5
    }

    vector = np.zeros(len(feature_cols))
    total = 0.0

    for act in actions:
        dish = act.get("dish")
        weight = weights.get(act.get("action"), 0.0)
        row = encoded_df[encoded_df["dish_name"] == dish]
        if not row.empty:
            vector += weight * row[feature_cols].values[0].astype(float)
            total += abs(weight)

    return vector / total if total > 0 else None


# --------------------- RANK AND COMBINE ---------------------
if st.button("🔍 Recommend Dishes"):
    user_vector = get_user_vector([a for a in st.session_state.actions if a["user_id"] == selected_user_id])
    inferred_timing = get_time_category(input_time)

    results = []
    for dish in menu_items:
        name = dish["dish_name"]
        try:
            # Calculate dish score based on nutritional factors and personalized factors
            base_score = calculate_dish_score(
                dish,
                hunger_level,
                user_live_goal,
                percentage_difference,
                default_factors,
                rule_factors
            )
        except Exception as e:
            st.warning(f"Error scoring dish '{name}': {e}")
            base_score = 0.0

        cosine_score = 0.0
        if user_vector is not None and name in encoded_df["dish_name"].values:
            row_vec = encoded_df[encoded_df["dish_name"] == name][feature_cols].values[0]
            cosine_score = cosine_similarity(user_vector.reshape(1, -1), row_vec.reshape(1, -1))[0][0]

        final_score = 0.7 * base_score + 0.3 * (cosine_score * 100)

        # Extract nutrients and other dish details (this assumes you have a function or logic to get them)
        dish_nutrients = extract_nutrients(dish)  # Make sure you define or replace this function

        # Append results with nutrients, timing category, and distributed percentage
        results.append({
            "dish_name": name,
            "final_score": round(final_score, 2),
            "base_score": round(base_score, 2),
            "cosine_score": round(cosine_score, 3),
            "nutrients": dish_nutrients,  # Nutrients included here
            "timing_category": dish.get("timing_category", "Not specified"),  # Extract timing category if present
            "distributed_percentage": dish.get("distributed_percentage", {})  # Extract distributed percentage
        })

    # Return as JSON structure instead of table
    final_results_json = json.dumps(results, indent=2)
    st.subheader("📊 Final Ranked Recommendations")
    st.json(final_results_json)  # Display as JSON

# --------------------- EXPORT LOG ---------------------
st.subheader("📅 Export Action Log")
if st.button("⬇️ Export as JSON"):
    with open("user_action_log.json", "w") as f:
        json.dump(st.session_state.actions, f, indent=2)
    st.success("Exported to user_action_log.json")

if st.checkbox("📋 Show Interaction Log"):
    st.json(st.session_state.actions)
