import string

class Customer:
    def __init__(self, id, email, first_name, last_name, phone, note) -> None:
        self.id = id
        self.first_name = string.capwords(first_name)
        self.last_name = string.capwords(last_name)
        self.full_name = self.first_name + " " + self.last_name
        self.email = email
        self.phone = phone
        self.spireCustomerNo = note

class Address:
    def __init__(self, first_name="", last_name="", address1=None, address2=None, city=None, province=None, province_code=None, postal_code=None, country=None, country_code=None, company=None, phone=None) -> None:
        self.first_name = string.capwords(first_name)
        self.last_name = string.capwords(last_name)
        self.full_name = (self.first_name + " " + self.last_name).strip()
        self.address1 = address1
        self.address2 = address2
        self.city = city
        self.province = province
        self.province_code = province_code
        self.postal_code = postal_code
        self.country = country
        self.country_code = country_code
        self.company = company
        self.phone = phone
        
class LineItem:
    def __init__(self, id, title, variant_name, grams, price, product_id, qty, sku, total_discount) -> None:
        self.id = id
        self.product_name = title
        self.variant_name = variant_name
        self.weight = str(round(grams/453.6, 3))
        
        self.price = price
        self.discount_amount = total_discount
        self.discount_percent = str(round((float(self.discount_amount) / float(self.price)) * 100, 3))
        self.net_price = str(float(self.price) - float(self.discount_amount))
        
        self.product_id = product_id
        self.order_qty = qty
        self.sku = sku
        
class Shipping:
    def __init__(self, code, title, source, discounted_price, discount_allocations) -> None:
        self.code = code
        self.title = title
        self.source = source
        self.freight_subtotal: float = float(discounted_price)       #Shipping price after line level discounts. Does not reflect cart or order level discounts
        
        disc_amt = 0
        if len(discount_allocations) != 0:
            #Shipping price has been discounted
            for alloc in discount_allocations:
                disc_amt += float(alloc["amount"])
                
        self.net_freight = self.freight_subtotal - disc_amt
        
        match code:
            case "Vaughan":
                self.is_pickup = True if self.code == "Vaughan" else False
                self.spire_shipVia_code = "01"                              #Pickup
            
            case "Local Delivery":
                self.spire_shipVia_code = "02"                              #Delivery
                
            case "custom":
                if title == "Local Delivery":
                    self.spire_shipVia_code = "02"
                else:
                    self.spire_shipVia_code = "03"                          #General Delivery
                    
            case "Free Shipping":
                self.spire_shipVia_code = "03"
                
            case code if "DOM." in code:
                self.spire_shipVia_code = "WEB-CP"                          #Canada Post
                
            case _:
                self.spire_shipVia_code = "03"