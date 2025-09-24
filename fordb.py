from backend import col
# Delete all documents in the collection
result = col.remark_collection.delete_many({})

print(f"{result.deleted_count} documents deleted.")