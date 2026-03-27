from stripe._stripe_object import StripeObject
obj = StripeObject.construct_from({"metadata": {"user_id": "99"}}, "api_key")
print("try get:", obj.metadata.get("user_id", None))
