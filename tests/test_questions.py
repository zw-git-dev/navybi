"""
Runs a curated set of realistically-phrased post-mission-reporting questions
through the NL query layer and prints what actually happened -- used to
produce QUESTION_TEST_LOG.md honestly, including the failures.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.nl_query import answer_question

QUESTIONS = [
    "What is the mission completion rate by unit?",
    "Show me the completion rate for Strike Fighter Squadron 12",
    "What is the completion rate for Search and Rescue missions?",
    "How is readiness looking by unit?",
    "Which equipment type has the lowest average readiness?",
    "What's the average duration of Deck Landing Qualification missions?",
    "Show me mission trends over the last 6 months",
    "How many missions occurred each month for Patrol Squadron 45?",
    "What's the weather like near the units?",
    "Compare completion rates between EOD and Rotary Wing communities",
    "What percentage of Carrier Air Wing 3 missions met their objective?",
    "readiness trend by month",
    "List all missions for Helicopter Sea Combat Sqn 7",
    "What is the average readiness of the Comms Suite equipment?",
    "Which unit has the most missions overall?",
    "What is our training currency rate by unit?",
    "What's the currency rate for Weapons Qualification?",
    "Show me training currency trends by month",
    "Which units have the most expired certifications?",
    "What is the average maintenance downtime by equipment type?",
    "What is our discrepancy resolution rate by unit?",
    "How much downtime does the Sensor Package have?",
    "What is the resolution rate for Strike Fighter Squadron 12?",
    "How many ASW Training missions were flown?",
    "Tell me about Deck Landing Qualification missions",
]

if __name__ == "__main__":
    for q in QUESTIONS:
        r = answer_question(q)
        print("=" * 80)
        print("Q:", q)
        print("understood:", r["understood"])
        if r["understood"]:
            print("sql:", r["sql"])
            print("rows returned:", len(r["df"]))
        print()
