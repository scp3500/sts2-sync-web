
import os
import re
import json

# The source of truth on the user's machine
base_path = r'D:\Desktop\slaythspire2\original_code'
cards_src_path = os.path.join(base_path, r'src\Core\Models\Cards')
pools_src_path = os.path.join(base_path, r'src\Core\Models\CardPools')
loc_file = os.path.join(base_path, r'localization\zhs\cards.json')
powers_loc_file = os.path.join(base_path, r'localization\zhs\powers.json')

# Output path in the current project
target_debug_file = r'd:\my-code\STS2_Sync\src-tauri\target\debug\STS2_Sync_Data\Data\cards.json'
resource_file = r'd:\my-code\STS2_Sync\src-tauri\resources\STS2_Sync_Data\Data\cards.json'
output_files = [target_debug_file, resource_file]

if not os.path.exists(loc_file):
    print(f"Error: Localization file not found: {loc_file}")
    exit(1)

with open(loc_file, 'r', encoding='utf-8') as f:
    loc_data = json.load(f)

powers_loc_data = {}
if os.path.exists(powers_loc_file):
    with open(powers_loc_file, 'r', encoding='utf-8') as f:
        powers_loc_data = json.load(f)

# Regex patterns
# Match: base(1, CardType.Skill, CardRarity.Uncommon, TargetType.AnyEnemy)
base_regex = re.compile(r'base\s*\(\s*(-?\d+)\s*,\s*(?:CardType\.)?(\w+)\s*,\s*(?:CardRarity\.)?(\w+)\s*,\s*(?:TargetType\.)?(\w+)\s*\)')

# Match: new DynamicVar("StrengthLoss", 8m) | new DamageVar(8m) | new PowerVar<VulnerablePower>(2m)
var_pattern = re.compile(r'new\s+(\w+Var)(?:<(\w+)>)?\s*\(\s*(?:"([^"]+)",\s*)?([^\s,)]+)')

# Match upgrade logic
upgrade_regex = re.compile(r'(?:\.|\[")(\w+)(?:"\])?\.UpgradeValueBy\(\s*(-?\d+\.?\d*)m?\s*\)')
upgrade_cost_regex = re.compile(r'SetUpgradeCost\s*\(\s*(\d+)\s*\)')

# Pool mapping regex
pool_card_regex = re.compile(r'ModelDb\.Card<(\w+)>')

def slugify(name):
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).upper()

def parse_num(s):
    s = s.strip().rstrip('m').rstrip('f')
    try:
        val = float(s)
        return int(val) if val == int(val) else val
    except:
        return 0

card_data = {}

# 1. Process all card source files
for filename in os.listdir(cards_src_path):
    if filename.endswith('.cs'):
        card_id = filename[:-3]
        slug = slugify(card_id)
        file_path = os.path.join(cards_src_path, filename)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            base_match = base_regex.search(content)
            if not base_match: continue
            
            cost = int(base_match.group(1))
            type_str = base_match.group(2).lower()
            rarity = base_match.group(3).lower()
            
            # Extract star cost
            star_cost_match = re.search(r'CanonicalStarCost\s*=>\s*(\d+)', content)
            star_cost = int(star_cost_match.group(1)) if star_cost_match else 0
            
            # Extract dynamic values
            values = {}
            for var_match in var_pattern.finditer(content):
                v_type = var_match.group(1)
                power_name = var_match.group(2)
                var_name = var_match.group(3)
                raw_val = var_match.group(4)
                
                key = var_name if var_name else (power_name if power_name else v_type.replace('Var', ''))
                if key.endswith("Power") and key != "Power": key = key[:-5]
                values[key] = parse_num(raw_val)

            # Extract upgrades
            upgrades = {}
            for up_match in upgrade_regex.finditer(content):
                v_name = up_match.group(1)
                v_val = parse_num(up_match.group(2))
                upgrades[v_name] = v_val
            
            # Extract upgrade cost changes
            up_cost_final = None
            
            # Pattern 1: SetUpgradeCost(X)
            up_cost_match = upgrade_cost_regex.search(content)
            if up_cost_match:
                up_cost_final = int(up_cost_match.group(1))
            
            # Pattern 2: EnergyCost.UpgradeBy(X) - usually inside OnUpgrade
            energy_up_match = re.search(r'EnergyCost\.UpgradeBy\(\s*(-?\d+)\s*\)', content)
            if energy_up_match:
                delta = int(energy_up_match.group(1))
                up_cost_final = cost + delta

            # Extract keywords
            canonical_keywords = []
            ck_match = re.search(r'CanonicalKeywords\s*=>\s*.*?\((.*?)\)', content, re.DOTALL)
            if ck_match:
                canonical_keywords = re.findall(r'CardKeyword\.(\w+)', ck_match.group(1))

            # Extract upgrade keyword changes
            upgrade_keywords_add = []
            upgrade_keywords_remove = []
            on_upgrade_match = re.search(r'protected override void OnUpgrade\(\)\s*\{(.*?)\}', content, re.DOTALL)
            if on_upgrade_match:
                up_content = on_upgrade_match.group(1)
                upgrade_keywords_add = re.findall(r'AddKeyword\s*\(\s*CardKeyword\.(\w+)\s*\)', up_content)
                upgrade_keywords_remove = re.findall(r'RemoveKeyword\s*\(\s*CardKeyword\.(\w+)\s*\)', up_content)

            # Extract flags
            has_overlay = "HasBuiltInOverlay => true" in content
            is_x_cost = "HasEnergyCostX => true" in content or "HasBuiltInEnergyCostX => true" in content
            is_star_x_cost = "HasStarCostX => true" in content or "HasBuiltInStarCostX => true" in content
            
            # Extract MaxUpgradeLevel
            max_upgrade_match = re.search(r'MaxUpgradeLevel\s*=>\s*(\d+)', content)
            max_upgrade = int(max_upgrade_match.group(1)) if max_upgrade_match else 1

            # Get description with fallback to powers.json
            description = loc_data.get(f"{slug}.description", "")
            if slug == "FERAL":
                description = "你每回合打出的第一张耗能为0{Energy:energyIcons()}的攻击牌，会放回你的[gold]手牌[/gold]。"
            elif not description:
                # Try SMART description first
                description = powers_loc_data.get(f"{slug}_POWER.smartDescription", "")
                if not description:
                    description = powers_loc_data.get(f"{slug}_POWER.description", "")
                
                # Map generic {Amount} to the actual variable name (e.g., {Skills:hide1()} for Burst)
                if "{Amount}" in description and values:
                    primary_var = list(values.keys())[0]
                    description = description.replace("{Amount}", "{" + primary_var + ":hide1()}")
                
                # Cleanup Godot style [blue] tags (remove completely as they don't change color in STS2 for this)
                description = description.replace("[blue]", "").replace("[/blue]", "")

            card_data[card_id] = {
                "id": card_id,
                "slug": slug,
                "name": loc_data.get(f"{slug}.title", card_id),
                "cost": cost,
                "is_x_cost": is_x_cost,
                "is_star_x_cost": is_star_x_cost,
                "max_upgrade": max_upgrade,
                "type": type_str,
                "rarity": rarity,
                "star_cost": star_cost,
                "has_overlay": has_overlay,
                "description": description,
                "values": values,
                "keywords": canonical_keywords,
                "upgrade": {
                    "damage_plus": upgrades.get("Damage", 0),
                    "block_plus": upgrades.get("Block", 0),
                    "cost": up_cost_final,
                    "values": upgrades,
                    "keywords_add": upgrade_keywords_add,
                    "keywords_remove": upgrade_keywords_remove
                }
            }

# 2. Process card pools to assign characters
character_map = {
    "IroncladCardPool": "ironclad", "SilentCardPool": "silent",
    "DefectCardPool": "defect", "NecrobinderCardPool": "necrobinder",
    "RegentCardPool": "regent", "ColorlessCardPool": "colorless",
    "CurseCardPool": "curse", "StatusCardPool": "status"
}

for filename in os.listdir(pools_src_path):
    if filename.endswith('.cs'):
        pool_name = filename[:-3]
        char = character_map.get(pool_name)
        if char:
            with open(os.path.join(pools_src_path, filename), 'r', encoding='utf-8') as f:
                pool_content = f.read()
                cards_in_pool = pool_card_regex.findall(pool_content)
                for c_id in cards_in_pool:
                    if c_id in card_data:
                        card_data[c_id]["character"] = char

# 3. Save to output
for output_file in output_files:
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(list(card_data.values()), f, ensure_ascii=False, indent=2)
    print(f"Successfully updated: {output_file}")

print(f"Successfully processed {len(card_data)} cards.")
