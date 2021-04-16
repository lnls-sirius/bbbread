BASIC_TAB = 0
ADVANCED_TAB = 1
SERVICE_TAB = 2
LOGS_TAB = 3

room_names = {
    "All": "",
    "Others": "Outros",
    "TL": "LTs",
    "Connectivity": "Conectividade",
    "Power Supplies": "Fontes",
    "RF": "RF",
}
# "LTs", "Conectividade", "Fontes", "RF", "Outros"
for i in range(20):
    room_names["IA-{:02d}".format(i + 1)] = "Sala{:02d}".format(i + 1)

COLORS = {"Dis": "red", "Con": "white", "BBB": "yellow"}
