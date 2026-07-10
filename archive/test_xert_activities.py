from integrations.xert import fetch_and_cache_xert_activity_list

activities = fetch_and_cache_xert_activity_list(days=60)

print(activities)