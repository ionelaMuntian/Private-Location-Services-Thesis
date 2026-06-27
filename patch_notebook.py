import json

path = r"C:\Users\ParaschivaMuntian\Documents\Ionela\Licenta\Private-Location-Services\notebooks\impossible_travel_model.ipynb"

with open(path, "r", encoding="utf-8") as f:
    nb = json.load(f)

def find_cell(nb, cell_id):
    for cell in nb["cells"]:
        if cell.get("id") == cell_id:
            return cell
    return None

def replace_lines(source, old, new):
    return [line.replace(old, new) for line in source]

# ---------- cc14: PT_PARAMS ----------
cc14 = find_cell(nb, "cc14")
assert cc14, "cc14 not found"
s = cc14["source"]
s = replace_lines(s, "n_estimators     = 200,", "n_estimators     = 300,")
s = replace_lines(s, "max_depth        = 4,      # reduced: depth 5 memorises the tiny positive class", "max_depth        = 5,")
s = replace_lines(s, "min_child_weight = 5,      # requires >= 5 samples per leaf -- prevents splits on single positives", "min_child_weight = 1,      # allow splits on individual anomaly samples")
s = replace_lines(s, "gamma            = 0.1,    # minimum loss reduction needed to make a split", "gamma            = 0.0,    # no minimum loss reduction requirement")
s = replace_lines(s, "reg_lambda       = 2.0,    # L2 regularisation on leaf weights", "reg_lambda       = 1.0,    # standard L2 regularisation")
cc14["source"] = s
print("cc14 fixed")

# ---------- cc16: CV_PARAMS ----------
cc16 = find_cell(nb, "cc16")
assert cc16, "cc16 not found"
s = cc16["source"]
s = replace_lines(s, "    min_child_weight = 5,\n", "    min_child_weight = 1,\n")
s = replace_lines(s, "    gamma            = 0.1,\n", "    gamma            = 0.0,\n")
s = replace_lines(s, "    reg_lambda       = 2.0,\n", "    reg_lambda       = 1.0,\n")
cc16["source"] = s
print("cc16 fixed")

# ---------- cc15: FHE_PARAMS ----------
cc15 = find_cell(nb, "cc15")
assert cc15, "cc15 not found"
new_src = []
skip_next = False
for line in cc15["source"]:
    if "n_estimators     = 30," in line:
        new_src.append(line.replace("n_estimators     = 30,", "n_estimators     = 40,"))
    elif "learning_rate    = 0.1," in line and "min_child_weight" not in "".join(new_src[-5:]):
        new_src.append(line)
        new_src.append("    min_child_weight = 1,\n")
        new_src.append("    gamma            = 0.0,\n")
    else:
        new_src.append(line)
cc15["source"] = new_src
print("cc15 fixed")

# ---------- cc17: threshold -> F1-max ----------
cc17 = find_cell(nb, "cc17")
assert cc17, "cc17 not found"
cc17["source"] = [
    "# 6b. Decision threshold calibration\n",
    "#\n",
    "# Uses pt_xgb on a 20% stratified hold-out.\n",
    "# Maximises F1 on the validation set -- more robust than fixed precision/recall\n",
    "# targets when the positive class is tiny (only ~20-30 positives in the val set).\n",
    "_, X_val, _, y_val = train_test_split(\n",
    "    X_train, y_train, test_size=0.2, stratify=y_train, random_state=SEED)\n",
    "\n",
    "y_val_proba = pt_xgb.predict_proba(X_val)[:, 1]\n",
    "\n",
    "prec_arr, rec_arr, thr_arr = precision_recall_curve(y_val, y_val_proba)\n",
    "\n",
    "f1_arr = np.where(\n",
    "    (prec_arr[:-1] + rec_arr[:-1]) > 0,\n",
    "    2 * prec_arr[:-1] * rec_arr[:-1] / (prec_arr[:-1] + rec_arr[:-1]),\n",
    "    0.0,\n",
    ")\n",
    "best_idx = int(np.argmax(f1_arr))\n",
    "DECISION_THRESHOLD = float(thr_arr[best_idx])\n",
    "best_p = float(prec_arr[best_idx])\n",
    "best_r = float(rec_arr[best_idx])\n",
    "\n",
    "print(f'Decision threshold   : {DECISION_THRESHOLD:.4f}')\n",
    "print(f'Validation precision : {best_p:.4f}')\n",
    "print(f'Validation recall    : {best_r:.4f}')\n",
    "print(f'Validation F1        : {f1_arr[best_idx]:.4f}')\n",
    "\n",
    "fig, ax = plt.subplots(figsize=(7, 4))\n",
    "ax.plot(rec_arr, prec_arr, color='steelblue', lw=2, label='PR curve')\n",
    "ax.scatter([best_r], [best_p], color='tomato', s=80, zorder=5,\n",
    "           label=f'F1-max threshold={DECISION_THRESHOLD:.3f}')\n",
    "ax.set_xlabel('Recall'); ax.set_ylabel('Precision')\n",
    "ax.set_title('Precision-Recall Curve (Validation Set)', fontweight='bold')\n",
    "ax.legend(); plt.tight_layout(); plt.show()"
]
print("cc17 fixed")

# ---------- save with LF endings, no BOM ----------
with open(path, "w", encoding="utf-8", newline="\n") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print("Saved. Verifying...")
with open(path, "rb") as f:
    first = f.read(4)
print(f"First bytes: {first} (should start with 0x7b = '{{' )")