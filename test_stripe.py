from stripe._stripe_object import StripeObject
obj = StripeObject(id="123", properties={"user_id": "456"})
# actually wait, let's just create a stripe object properly
obj = StripeObject.construct_from({"metadata": {"user_id": "99"}}, "api_key")
print("metadata user_id:", getattr(obj.metadata, "user_id", None))
