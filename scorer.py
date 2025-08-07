def get_time_category(input_time):
    current_time = datetime.strptime(input_time, "%H:%M").time()
    if 6 <= current_time.hour < 10: return "Breakfast"
    elif 10 <= current_time.hour < 12: return "Brunch"
    elif 12 <= current_time.hour < 17: return "Lunch"
    elif 17 <= current_time.hour < 22: return "Dinner"
    elif 22 <= current_time.hour < 24 or 0 <= current_time.hour < 2: return "Midnight Snack"
    else: return "Snack"

def get_matching_timing_categories(inferred):
    return {
        "Breakfast": ["Breakfast"],
        "Brunch": ["Brunch", "Lunch", "Dinner"],
        "Lunch": ["Brunch", "Lunch", "Dinner"],
        "Dinner": ["Brunch", "Lunch", "Dinner"],
        "Snack": ["Snack", "Midnight Snack"],
        "Midnight Snack": ["Snack", "Midnight Snack"]
    }.get(inferred, [])

def get_suggested_meal_categories(inferred):
    return {
        "Breakfast": ["Main Course", "Salad", "Drink"],
        "Lunch": ["Main Course", "Side Dish", "Starter", "Soup"],
        "Brunch": ["Main Course", "Side Dish", "Starter", "Soup"],
        "Dinner": ["Main Course", "Side Dish", "Starter", "Soup"],
        "Snack": ["Starter", "Soup", "Salad", "Main Course", "Side Dish", "Dessert", "Drink", "Snack"],
        "Midnight Snack": ["Starter", "Soup", "Salad", "Main Course", "Side Dish", "Dessert", "Drink", "Snack"]
    }.get(inferred, [])

def filter_dishes(menu, timing_categories, meal_categories):
    filtered = []
    for dish in menu:
        timing = dish.get('timing_category')
        dish_type = dish.get('dish_type')
        if not isinstance(dish_type, list): dish_type = [dish_type]
        if not isinstance(timing, list): timing = [timing]
        if any(t in timing for t in timing_categories) and any(m in dish_type for m in meal_categories):
            filtered.append(dish)
    return filtered

def get_nutrients_data(dish):
    
    nutrients_data = dish.get("dish_variants", {}).get("normal", {}).get("full", {}).get("nutrients", {})

    # List of nutrients to extract
    nutrients_to_extract = ['ENERC','PROTCNT','CHOAVLDF','FATCE','FIBTG','FASAT','TCHO','CHOLC','NA','TOTALFREESUGARS']

    # Extract quantities for the specified nutrients
    nutrient_quantities = {nutrient: next(item['quantity'] for item in nutrients_data if item['name'] == nutrient) 
                        for nutrient in nutrients_to_extract}

    return nutrient_quantities

# Function to calculate the score for each dish based on various factors
def calculate_dish_score(
    dish: dict,
    hunger_level: str,
    user_live_goal: dict,
    percentage_difference: dict,
    default_factors: dict,
    rule_factors: dict
) -> float:
    epsilon = 1e-6

    def get_macro_value(macro_list, key):
        for item in macro_list:
            if item.get("name") == key:
                return item.get("value", 0.0)
        return 0.0

    def safe_percentage(value):
        try:
            return float(str(value).replace("%", "").strip())
        except:
            return 0.0

    # Extract raw values
    serving_size = float(dish.get("dish_variants", {}).get("normal", {}).get("full", {}).get("serving", {}).get("size", 0.0))
    macro_nutrients = dish.get("dish_variants", {}).get("normal", {}).get("full", {}).get("calculate_nutrients", {}).get("macro_nutrients", [])
    dish_nutrients_data = get_nutrients_data(dish)

    # Raw nutrients
    saturated_fat = dish_nutrients_data.get("FASAT", 0.0)
    polyunsaturated_fat = dish_nutrients_data.get("FAPU", 0.0)
    monounsaturated_fat = dish_nutrients_data.get("FAMU", 0.0)
    cholesterol = dish_nutrients_data.get("CHOLC", 0.0)
    sodium = dish_nutrients_data.get("NA", 0.0)
    sugar = dish_nutrients_data.get("TOTALFREESUGARS", 0.0)
    sugar_pct = sugar * 100 / serving_size if serving_size > 0 else 0.0

    distributed_percentage = dish.get("distributed_percentage", {})
    protein_dish_percentage = safe_percentage(distributed_percentage.get("proteins"))
    carbs_dish_percentage = safe_percentage(distributed_percentage.get("carbs"))
    fats_dish_percentage = safe_percentage(distributed_percentage.get("fats"))
    fiber_dish_percentage = safe_percentage(distributed_percentage.get("fibers"))

    # Extract macro values
    dish_energy = get_macro_value(macro_nutrients, "energy")
    dish_protein = get_macro_value(macro_nutrients, "proteins")
    dish_carbs = get_macro_value(macro_nutrients, "carbs")
    dish_fats = get_macro_value(macro_nutrients, "fats")
    dish_fibers = get_macro_value(macro_nutrients, "fibers")

    # Live goals
    live_goal_energy = user_live_goal.get("energy", 300)
    live_goal_protein = user_live_goal.get("proteins", 22)
    live_goal_carbs = user_live_goal.get("carbs", 22)
    live_goal_fats = user_live_goal.get("fats", 19)
    live_goal_fibers = user_live_goal.get("fibers", 7)

    # Dynamic weighting
    live_protien_factor = default_factors.get("protein", 1) * (1 + percentage_difference.get("proteins", 0) / 100)
    live_carbs_factor = default_factors.get("carbs", 1) * (1 + percentage_difference.get("carbs", 0) / 100)
    live_fats_factor = default_factors.get("fats", 1) * (1 + percentage_difference.get("fats", 0) / 100)
    live_fiber_factor = default_factors.get("fibers", 1) * (1 + percentage_difference.get("fibers", 0) / 100)
    live_energy_factor = default_factors.get("energy", 1) * (1 + percentage_difference.get("energy", 0) / 100)

    # Density Score
    protein_goal_pct = (live_goal_protein * 4) / live_goal_energy * 100
    carbs_goal_pct = (live_goal_carbs * 4) / live_goal_energy * 100
    fats_goal_pct = (live_goal_fats * 9) / live_goal_energy * 100
    fiber_goal_pct = (live_goal_fibers * 2) / live_goal_energy * 100

    score_protein = live_protien_factor * min(1, protein_dish_percentage / (protein_goal_pct or 1))
    score_carbs = live_carbs_factor * min(1, carbs_dish_percentage / (carbs_goal_pct or 1))
    score_fats = live_fats_factor * min(1, fats_dish_percentage / (fats_goal_pct or 1))
    score_fiber = live_fiber_factor * min(1, fiber_dish_percentage / (fiber_goal_pct or 1))
    score_energy = live_energy_factor * min(1, dish_energy / (live_goal_energy + epsilon))

    density_score = (score_protein + score_carbs + score_fats + score_fiber + score_energy) * 100 / (
        live_protien_factor + live_carbs_factor + live_fats_factor + live_fiber_factor + live_energy_factor + epsilon
    )

    # Euclidean distance
    euclidean_components = [
        (dish_protein, live_goal_protein, live_protien_factor),
        (dish_carbs, live_goal_carbs, live_carbs_factor),
        (dish_fats, live_goal_fats, live_fats_factor),
        (dish_fibers, live_goal_fibers, live_fiber_factor),
        (dish_energy, live_goal_energy, live_energy_factor)
    ]
    euclidean_score = 0
    penalty = False
    for actual, goal, weight in euclidean_components:
        dist = abs(actual - goal)
        if dist > 30:
            penalty = True
        score = max(0, min(100, (1 - dist / (goal + epsilon)) * 100))
        euclidean_score += score * weight

    euclidean_distance_score = euclidean_score / (
        live_protien_factor + live_carbs_factor + live_fats_factor + live_fiber_factor + live_energy_factor + epsilon
    )
    if penalty:
        euclidean_distance_score *= 0.2

    # Satiety Score
    dish_energy = dish_energy or 1
    satiety_score = (
        live_protien_factor * (dish_protein / dish_energy) +
        live_carbs_factor * (dish_carbs / dish_energy) +
        live_fats_factor * (dish_fats / dish_energy) +
        live_fiber_factor * (dish_fibers / dish_energy)
    )
    satiety_map = {
        "High": 1 + (-0.3) * satiety_score,
        "Medium": 1,
        "Low": 1 + (0.5) * satiety_score
    }
    scaled_satiety_score = satiety_map.get(hunger_level, 1) * 100 / 5

    # Rule scores
    protein_overrule_score = protein_overrule(distributed_percentage)
    low_carbs_overrule_score = low_carbs_overrule(distributed_percentage)
    low_fat_overrule_score = low_fat_overrule(distributed_percentage)
    sugar_content_rule_score = sugar_content_rule(sugar_pct)
    sodium_content_rule_score = sodium_content_rule(sodium, serving_size)
    saturated_fat_rule_score = saturated_fat_rule(saturated_fat, serving_size)
    cholesterol_rule_score = cholesterol_rule(cholesterol, serving_size)
    caloric_density_rule_score = caloric_density_rule(dish_energy, serving_size)
    good_fats_score = good_fats_rule(saturated_fat, polyunsaturated_fat, monounsaturated_fat, serving_size)

    # Final weighted score
    final_dish_score = (
        (density_score * default_factors.get("density_factor", 1)) +
        (scaled_satiety_score * default_factors.get("satiety_factor", 1)) +
        (euclidean_distance_score * default_factors.get("euclidean_factor", 1)) +
        (protein_overrule_score * rule_factors.get("protein_overrule_factor", 1)) +
        (low_carbs_overrule_score * rule_factors.get("low_carbs_overrule_factor", 1)) +
        (low_fat_overrule_score * rule_factors.get("low_fat_overrule_factor", 1)) +
        (sugar_content_rule_score * rule_factors.get("sugar_content_factor", 1)) +
        (sodium_content_rule_score * rule_factors.get("sodium_content_factor", 1)) +
        (saturated_fat_rule_score * rule_factors.get("saturated_fat_factor", 1)) +
        (cholesterol_rule_score * rule_factors.get("cholesterol_factor", 1)) +
        (caloric_density_rule_score * rule_factors.get("caloric_density_factor", 1)) +
        (good_fats_score * rule_factors.get("good_fats_factor", 1))
    ) / (
        default_factors.get("density_factor", 1) +
        default_factors.get("satiety_factor", 1) +
        default_factors.get("euclidean_factor", 1) +
        sum(rule_factors.values()) +
        epsilon
    )

    return final_dish_score


def protein_overrule(distributed_percentage):
    try:
        # Extract percentages and convert to float
        protein = float(distributed_percentage.get("proteins", "0").replace("%", ""))
        carbs = float(distributed_percentage.get("carbs", "0").replace("%", ""))
        fats = float(distributed_percentage.get("fats", "0").replace("%", ""))

        # Initialize score
        score = 100

        # Protein score (ideal range: 8–43%)
        if 8 <= protein <= 43:
            protein_score = 100  # Full points for ideal protein range
        else:
            # Penalize based on how far protein is from the ideal range
            protein_distance = min(abs(protein - 8), abs(protein - 43))
            protein_score = max(0, 100 - protein_distance * 2)  # Reduce score by 2 per percentage point deviation

        # Carbs penalty (if >65%)
        carbs_penalty = 0
        if carbs > 65:
            carbs_penalty = (carbs - 65) * 1.5  # Penalize 1.5 points per percentage point above 65

        # Fats penalty (if >30%)
        fats_penalty = 0
        if fats > 30:
            fats_penalty = (fats - 30) * 1.5  # Penalize 1.5 points per percentage point above 30

        # Calculate final score (weights: protein 50%, carbs 25%, fats 25%)
        score = (protein_score * 0.5) - (carbs_penalty * 0.25) - (fats_penalty * 0.25)
        score = max(0, min(100, round(score)))  # Ensure score is between 0 and 100

        return score

    except (KeyError, ValueError) as e:
        return 0  # Return 0 for invalid input

def low_carbs_overrule(dish):
    try:
        # Extract percentages and convert to float
        dist = dish.get("distributed_percentage", {})
        protein = float(dist.get("proteins", "0").replace("%", ""))
        carbs = float(dist.get("carbs", "0").replace("%", ""))
        fats = float(dist.get("fats", "0").replace("%", ""))

        # Initialize score
        score = 100

        # Carbs score (ideal range: 45–60%)
        if 45 <= carbs <= 60:
            carbs_score = 100  # Full points for ideal carb range
        else:
            # Penalize based on distance from nearest boundary (45% or 60%)
            carbs_distance = min(abs(carbs - 45), abs(carbs - 60))
            carbs_score = max(0, 100 - carbs_distance * 2)  # Reduce by 2 per percentage point deviation

        # Protein score
        protein_score = 0
        if 8 <= protein <= 43:
            protein_score = 100  # Full points for primary protein range
        elif 3 <= protein <= 8 or 44 <= protein <= 58:
            protein_score = 80  # Slightly lower score for secondary range
        else:
            # Penalize based on distance from nearest acceptable boundary
            if protein < 3:
                protein_distance = abs(protein - 3)
            elif 8 < protein < 44:
                protein_distance = min(abs(protein - 8), abs(protein - 44))
            else:
                protein_distance = abs(protein - 58)
            protein_score = max(0, 80 - protein_distance * 2)  # Reduce by 2 per percentage point deviation

        # Fats penalty
        fats_penalty = 0
        if 8 <= protein <= 43:
            if fats > 35:
                fats_penalty = (fats - 35) * 1.5  # Penalize 1.5 points per percentage point above 35
        elif 3 <= protein <= 8 or 44 <= protein <= 58:
            if fats > 10:
                fats_penalty = (fats - 10) * 2  # Stricter penalty: 2 points per percentage point above 10
        else:
            # For protein outside acceptable ranges, apply a moderate penalty if fats are high
            if fats > 35:
                fats_penalty = (fats - 35) * 1.5

        # Calculate final score (weights: carbs 40%, protein 40%, fats 20%)
        score = (carbs_score * 0.4) + (protein_score * 0.4) - (fats_penalty * 0.2)
        score = max(0, min(100, round(score)))  # Ensure score is between 0 and 100

        return score

    except (KeyError, ValueError):
        return 0  # Return 0 for invalid input
    
def low_fat_overrule(dish):
    try:
        # Extract percentages and convert to float
        dist = dish.get("distributed_percentage", {})
        protein = float(dist.get("proteins", "0").replace("%", ""))
        carbs = float(dist.get("carbs", "0").replace("%", ""))
        fats = float(dist.get("fats", "0").replace("%", ""))

        # Initialize score
        score = 100

        # Fats score (ideal range: 15–30%)
        if 15 <= fats <= 30:
            fats_score = 100  # Full points for ideal fat range
        else:
            # Penalize based on distance from nearest boundary (15% or 30%)
            fats_distance = min(abs(fats - 15), abs(fats - 30))
            fats_score = max(0, 100 - fats_distance * 2)  # Reduce by 2 per percentage point deviation

        # Protein score
        protein_score = 0
        if 8 <= protein <= 43:
            protein_score = 100  # Full points for primary protein range
        elif 3 <= protein <= 8 or 44 <= protein <= 58:
            protein_score = 80  # Slightly lower score for secondary range
        else:
            # Penalize based on distance from nearest acceptable boundary
            if protein < 3:
                protein_distance = abs(protein - 3)
            elif 8 < protein < 44:
                protein_distance = min(abs(protein - 8), abs(protein - 44))
            else:
                protein_distance = abs(protein - 58)
            protein_score = max(0, 80 - protein_distance * 2)  # Reduce by 2 per percentage point deviation

        # Carbs penalty
        carbs_penalty = 0
        if 8 <= protein <= 43:
            if carbs > 65:
                carbs_penalty = (carbs - 65) * 1.5  # Penalize 1.5 points per percentage point above 65
        elif 3 <= protein <= 8 or 44 <= protein <= 58:
            if carbs > 60:
                carbs_penalty = (carbs - 60) * 2  # Stricter penalty: 2 points per percentage point above 60
        else:
            # For protein outside acceptable ranges, apply a moderate penalty for carbs > 65
            if carbs > 65:
                carbs_penalty = (carbs - 65) * 1.5

        # Calculate final score (weights: fats 40%, protein 40%, carbs 20%)
        score = (fats_score * 0.4) + (protein_score * 0.4) - (carbs_penalty * 0.2)
        score = max(0, min(100, round(score)))  # Ensure score is between 0 and 100

        return score

    except (KeyError, ValueError):
        return 0  # Return 0 for invalid input
    
def sugar_content_rule(sugar_pct):
    try:
        # Convert sugar_pct to float
        sugar = float(sugar_pct)

        # Initialize score
        score = 100

        # Apply penalties based on sugar percentage thresholds
        if sugar <= 10:
            score = 100  # Full score for low sugar (≤10%)
        elif 10 < sugar <= 20:
            # Moderate penalty for sugar between 10% and 20%
            score = max(0, 100 - (sugar - 10) * 2)  # Reduce by 2 points per percentage point above 10
            # print(score)
        elif 20 < sugar <= 30:
            # Higher penalty for sugar between 20% and 30%
            score = max(0, 80 - (sugar - 20) * 3)  # Start at 80, reduce by 3 points per percentage point above 20
            # print(score)
        else:  # sugar > 30
            # Severe penalty for sugar above 30%
            score = max(0, 50 - (sugar - 30) * 4)  # Start at 50, reduce by 4 points per percentage point above 30
            # print(score)

        return round(score)  # Return rounded score between 0 and 100

    except (TypeError, ValueError):
        return 0  # Return 0 for invalid input

def sodium_content_rule(sodium, serving_size):
    try:
        # Calculate sodium per 100g
        sodium_per_100g = (float(sodium) * 100) / float(serving_size) if serving_size > 0 else 0.0

        # Initialize score
        score = 100

        # Apply penalties based on sodium per 100g thresholds
        if sodium_per_100g <= 400:
            score = 100  # Full score for low sodium (≤400 mg)
        elif 400 < sodium_per_100g <= 800:
            # Moderate penalty for sodium between 400 and 800 mg
            score = max(0, 100 - (sodium_per_100g - 400) * 0.05)  # Reduce by 0.05 points per mg above 400
        elif 800 < sodium_per_100g <= 1200:
            # Higher penalty for sodium between 800 and 1200 mg
            score = max(0, 80 - (sodium_per_100g - 800) * 0.075)  # Start at 80, reduce by 0.075 points per mg above 800
        else:  # sodium_per_100g > 1200
            # Severe penalty for sodium above 1200 mg
            score = max(0, 50 - (sodium_per_100g - 1200) * 0.1)  # Start at 50, reduce by 0.1 points per mg above 1200

        return round(score)  # Return rounded score between 0 and 100

    except (TypeError, ValueError, ZeroDivisionError):
        return 0  # Return 0 for invalid input

def saturated_fat_rule(saturated_fat, serving_size):
    try:
        # Calculate saturated fat per 100g
        saturated_fat_per_100g = (float(saturated_fat) * 100) / float(serving_size) if serving_size > 0 else 0.0

        # Initialize score
        score = 100

        # Apply penalties based on saturated fat per 100g thresholds
        if saturated_fat_per_100g <= 2000:
            score = 100  # Full score for low saturated fat (≤2000 mg)
        elif 2000 < saturated_fat_per_100g <= 5000:
            # Moderate penalty for saturated fat between 2000 and 5000 mg
            score = max(0, 100 - (saturated_fat_per_100g - 2000) * 0.033)  # Reduce by 0.033 points per mg above 2000
        elif 5000 < saturated_fat_per_100g <= 7000:
            # Higher penalty for saturated fat between 5000 and 7000 mg
            score = max(0, 80 - (saturated_fat_per_100g - 5000) * 0.05)  # Start at 80, reduce by 0.05 points per mg above 5000
        else:  # saturated_fat_per_100g > 7000
            # Severe penalty for saturated fat above 7000 mg
            score = max(0, 50 - (saturated_fat_per_100g - 7000) * 0.067)  # Start at 50, reduce by 0.067 points per mg above 7000

        return round(score)  # Return rounded score between 0 and 100

    except (TypeError, ValueError, ZeroDivisionError):
        return 0  # Return 0 for invalid input

def cholesterol_rule(cholesterol, serving_size):
    try:
        # Calculate cholesterol per 100g
        cholesterol_per_100g = (float(cholesterol) * 100) / float(serving_size) if serving_size > 0 else 0.0

        # Initialize score
        score = 100

        # Apply penalties based on cholesterol per 100g thresholds
        if cholesterol_per_100g <= 75:
            score = 100  # Full score for low cholesterol (≤75 mg)
        elif 75 < cholesterol_per_100g <= 150:
            # Moderate penalty for cholesterol between 75 and 150 mg
            score = max(0, 100 - (cholesterol_per_100g - 75) * 0.266)  # Reduce by 0.266 points per mg above 75
        elif 150 < cholesterol_per_100g <= 200:
            # Higher penalty for cholesterol between 150 and 200 mg
            score = max(0, 80 - (cholesterol_per_100g - 150) * 0.4)  # Start at 80, reduce by 0.4 points per mg above 150
        else:  # cholesterol_per_100g > 200
            # Severe penalty for cholesterol above 200 mg
            score = max(0, 60 - (cholesterol_per_100g - 200) * 0.5)  # Start at 60, reduce by 0.5 points per mg above 200

        return round(score)  # Return rounded score between 0 and 100

    except (TypeError, ValueError, ZeroDivisionError):
        return 0  # Return 0 for invalid input

def caloric_density_rule(energy, serving_size):
    try:
        # Calculate caloric density per 100g
        caloric_density = (float(energy) * 100) / float(serving_size) if serving_size > 0 else 0.0

        # Initialize score
        score = 100

        # Apply penalties based on caloric density thresholds
        if caloric_density <= 200:
            score = 100  # Full score for low caloric density (≤200 kcal)
        elif 200 < caloric_density <= 300:
            # Moderate penalty for caloric density between 200 and 300 kcal
            score = max(0, 100 - (caloric_density - 200) * 0.2)  # Reduce by 0.2 points per kcal above 200
        elif 300 < caloric_density <= 400:
            # Higher penalty for caloric density between 300 and 400 kcal
            score = max(0, 80 - (caloric_density - 300) * 0.3)  # Start at 80, reduce by 0.3 points per kcal above 300
        else:  # caloric_density > 400
            # Severe penalty for caloric density above 400 kcal
            score = max(0, 50 - (caloric_density - 400) * 0.4)  # Start at 50, reduce by 0.4 points per kcal above 400

        return round(score)  # Return rounded score between 0 and 100

    except (TypeError, ValueError, ZeroDivisionError):
        return 0  # Return 0 for invalid input

def good_fats_rule(saturated_fat, polyunsaturated_fat, monounsaturated_fat, serving_size):
    try:
        # Calculate good fats per 100g
        good_fats = float(polyunsaturated_fat) + float(monounsaturated_fat)
        good_fats_per_100g = (good_fats * 100) / float(serving_size) if serving_size > 0 else 0.0

        # Initialize score
        score = 100

        # Scoring logic based on good fats per 100g
        if good_fats_per_100g <= 500:
            # Low good fats: lower score
            score = max(0, 50 + (good_fats_per_100g / 500) * 30)  # Scale from 50 (0 mg) to 80 (500 mg)
        elif 500 < good_fats_per_100g <= 2000:
            # Moderate good fats: moderate score
            score = max(80, 80 + ((good_fats_per_100g - 500) / 1500) * 10)  # Scale from 80 (500 mg) to 90 (2000 mg)
        else:  # good_fats_per_100g > 2000
            # High good fats: high score
            score = min(100, 90 + ((good_fats_per_100g - 2000) / 1000) * 5)  # Scale from 90 (2000 mg) to 100 (3000+ mg)

        return round(score)  # Return rounded score between 0 and 100

    except (TypeError, ValueError, ZeroDivisionError):
        return 0  # Return 0 for invalid input

def fiber_content_rule(fiber, carbohydrates, serving_size, has_essential_nutrients):
    try:
        # Avoid division by zero
        if serving_size <= 0 or carbohydrates <= 0:
            return 0

        # Convert fiber and carbs to per 100g
        fiber_per_100g = (float(fiber) * 100) / float(serving_size)
        carbs_per_100g = (float(carbohydrates) * 100) / float(serving_size)
        fiber_ratio = (fiber_per_100g / carbs_per_100g) * 100 if carbs_per_100g > 0 else 0.0

        # Initialize score
        score = 100

        # Fiber ratio score (based on 2.5%, 5%, 10% thresholds)
        if fiber_ratio <= 2.5:
            # Low fiber ratio: low score
            fiber_ratio_score = max(0, 50 + (fiber_ratio / 2.5) * 20)  # Scale from 50 (0%) to 70 (2.5%)
        elif 2.5 < fiber_ratio <= 5:
            # Moderate fiber ratio: moderate score
            fiber_ratio_score = max(70, 70 + ((fiber_ratio - 2.5) / 2.5) * 10)  # Scale from 70 (2.5%) to 80 (5%)
        elif 5 < fiber_ratio <= 10:
            # Good fiber ratio: higher score
            fiber_ratio_score = max(80, 80 + ((fiber_ratio - 5) / 5) * 10)  # Scale from 80 (5%) to 90 (10%)
        else:  # fiber_ratio > 10
            # High fiber ratio: highest score
            fiber_ratio_score = min(100, 90 + ((fiber_ratio - 10) / 5) * 5)  # Scale from 90 (10%) to 100 (15%+)

        # Fiber per 100g score (based on 1.5g, 2.5g thresholds)
        if fiber_per_100g <= 1.5:
            # Low fiber per 100g: low score
            fiber_per_100g_score = max(0, 50 + (fiber_per_100g / 1.5) * 20)  # Scale from 50 (0g) to 70 (1.5g)
        elif 1.5 < fiber_per_100g <= 2.5:
            # Moderate fiber per 100g: moderate score
            fiber_per_100g_score = max(70, 70 + ((fiber_per_100g - 1.5) / 1) * 10)  # Scale from 70 (1.5g) to 80 (2.5g)
        else:  # fiber_per_100g > 2.5
            # High fiber per 100g: high score
            fiber_per_100g_score = min(100, 80 + ((fiber_per_100g - 2.5) / 2.5) * 15)  # Scale from 80 (2.5g) to 95 (5g+)

        # Essential nutrients bonus
        nutrients_bonus = 10 if has_essential_nutrients else 0

        # Calculate final score (weights: fiber ratio 40%, fiber per 100g 40%, nutrients 20%)
        score = (fiber_ratio_score * 0.4) + (fiber_per_100g_score * 0.4) + (nutrients_bonus * 0.2)
        score = max(0, min(100, round(score)))  # Ensure score is between 0 and 100

        return score

    except (TypeError, ValueError, ZeroDivisionError):
        return 0  # Return 0 for invalid input
