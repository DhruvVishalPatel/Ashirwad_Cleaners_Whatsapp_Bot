import streamlit as st
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()

# We can import directly from our app modules since dashboard.py is at the root
from app.core.database import SessionLocal
from app.models.schemas import Order, OrderStatus, PaymentStatus, Customer, OrderType, Runner
from app.services.whatsapp_sender import send_text_message
from app.services.crud import create_customer, create_order, get_customer, get_runners, create_runner, update_customer_name, get_available_points

st.set_page_config(page_title="Ashirwad Cleaners Admin", layout="wide")

st.title("🧺 Ashirwad Cleaners: Admin Dashboard")

# Initialize database session
db = SessionLocal()

# ----- SCOREBOARD METRICS -----
st.markdown("### 📊 Live Analytics")
metric_col1, metric_col2, metric_col3 = st.columns(3)

total_customers = db.query(Customer).count()
active_orders_count = db.query(Order).filter(~Order.status.in_([OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.REJECTED])).count()
pending_pickups = db.query(Order).filter(Order.status == OrderStatus.PENDING_PICKUP).count()

metric_col1.metric("Active Orders", active_orders_count)
metric_col2.metric("Pending Pickups", pending_pickups)
metric_col3.metric("Total Customers", total_customers)

st.markdown("---")

# ----- SIDEBAR LOGIC (HIDDEN FOR NOW) -----
_DROP_OFF_CODE_STORED = """
with st.sidebar:
    st.header("🏢 Walk-in Store Drop-off")
    st.markdown("Manually enter a customer who walked into the store.")
    
    with st.form("manual_entry_form"):
        manual_phone = st.text_input("Customer Phone Number")
        manual_name = st.text_input("Customer Name (Leave blank if existing)")
        manual_service_list = st.multiselect("Service Category", ["Dry Clean", "Washing", "Steam Press"], default=["Dry Clean"])
        manual_items = st.number_input("Item Count", min_value=1, value=1)
        manual_amount = st.number_input("Total Amount (₹)", min_value=0.0, value=0.0, step=10.0)
        manual_instructions = st.text_area("Special Instructions (Optional)")
        
        submitted = st.form_submit_button("Create Drop-off Order")
        
        if submitted:
            if not manual_phone:
                st.error("Phone number is required.")
            elif manual_amount <= 0:
                st.error("Please enter the total amount to be paid.")
            else:
                cust = get_customer(db, manual_phone)
                if not cust:
                    cust = create_customer(db, manual_phone, name=manual_name)
                elif manual_name:
                    update_customer_name(db, cust.customer_id, manual_name)
                
                manual_service = ", ".join(manual_service_list)
                
                # Create the order
                new_order = create_order(
                    db, 
                    cust.customer_id, 
                    manual_items, 
                    order_type="STORE_DROP",
                    service_category=manual_service,
                    flat_address="N/A (Store Drop)",
                    estimated_amount=manual_amount,
                    delivery_fee=0.0,
                    special_instructions=manual_instructions if manual_instructions else "None",
                    disclaimer_accepted=True
                )
                new_order.total_amount = manual_amount
                new_order.status = OrderStatus.IN_SHOP # Walk-ins start IN_SHOP
                db.commit()
                st.success(f"Created Order #{new_order.order_id} successfully!")
"""

# ----- TABS -----
tab1, tab2, tab3 = st.tabs(["📋 Active Orders", "👥 Customer Database", "⚙️ Staff Settings"])

def load_active_orders(show_all=False):
    if show_all:
        orders = db.query(Order).all()
    else:
        # Fetch active orders
        orders = db.query(Order).filter(~Order.status.in_([OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.REJECTED])).all()
    
    data = []
    for o in orders:
        delivery_fee = getattr(o, "delivery_fee", 0.0)
        raw_est = o.estimated_amount or 0.0
        raw_total = o.total_amount or 0.0
        
        data.append({
            "Order ID": o.order_id,
            "Type": o.order_type.name,
            "Service(s)": o.service_category or "Dry Clean",
            "Customer Name": o.customer.name if o.customer and o.customer.name else "Unknown",
            "Customer Phone": o.customer.phone_number if o.customer else "Unknown",
            "Text Address": o.flat_address or "N/A",
            "GPS Location": o.customer.last_location_gps if o.customer and o.customer.last_location_gps else "N/A",
            "Items": o.item_count,
            "Final Total": f"₹{raw_total + delivery_fee - o.points_redeemed}" if o.total_amount else f"₹{raw_est + delivery_fee - o.points_redeemed}",
            "Payment": o.payment_status.name,
            "Status": o.status.name
        })
    return pd.DataFrame(data), orders

with tab1:
    show_all = st.checkbox("Show all orders (including delivered)", value=False)
    df, raw_orders = load_active_orders(show_all)
    
    if df.empty:
        st.info("No orders found matching the criteria.")
    else:
        st.dataframe(df, use_container_width=True)
    
    st.markdown("---")
    st.subheader("Manage Order")
    
    # Selection box
    manageable_orders = [o for o in raw_orders if o.status.name not in ["CANCELLED", "REJECTED"]]
    order_id_list = [o.order_id for o in manageable_orders]
    
    selected_id = None
    if not order_id_list:
        st.info("No active orders to manage.")
    else:
        selected_id = st.selectbox("Select Order to Manage:", order_id_list)
        
    if selected_id:
        # Get the selected order object
        order = next(o for o in raw_orders if o.order_id == selected_id)
        
        with st.container(border=True):
            st.markdown(f"#### Order #{order.order_id} Details")
            st.markdown(f"**Services Requested:** {order.service_category}")
            st.markdown(f"**Pickup Address:** {order.flat_address}")
            
            if order.items:
                st.markdown("**Itemized Garments:**")
                for oi in order.items:
                    st.markdown(f"- {oi.quantity}x {oi.garment_type} ({oi.service_type})")
            else:
                st.markdown("*(No itemized breakdown available for this order)*")
                
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Update Price
            st.markdown("**Update Final Price**")
            
            raw_val = float(order.total_amount or order.estimated_amount or 0.0)
            delivery_fee = getattr(order, "delivery_fee", 0.0)
            points_redeemed = getattr(order, "points_redeemed", 0)
            
            st.markdown(f"*(Raw Estimate was: ₹{order.estimated_amount or 0.0})*")
            new_raw_price = st.number_input("Raw Clothes Amount (₹)", min_value=0.0, value=raw_val, step=10.0)
            
            st.markdown(f"**+ Delivery Fee:** ₹{delivery_fee}")
            if points_redeemed > 0:
                st.markdown(f"**- Points Redeemed:** ₹{points_redeemed}")
            st.markdown(f"**= Final Total to Collect:** ₹{new_raw_price + delivery_fee - points_redeemed}")
            
            if st.button("Save Price"):
                order.total_amount = new_raw_price
                db.commit()
                st.success(f"Raw Price saved as ₹{new_raw_price}")
                st.rerun()
                
        with col2:
            # Update Payment & Order Status
            st.markdown("**Update Status**")
            new_payment = st.selectbox("Payment Status", [p.name for p in PaymentStatus], index=[p.name for p in PaymentStatus].index(order.payment_status.name))
            valid_statuses = [s.name for s in OrderStatus if s.name not in ["CANCELLED", "REJECTED"]]
            default_idx = valid_statuses.index(order.status.name) if order.status.name in valid_statuses else 0
            new_status = st.selectbox("Order Status", valid_statuses, index=default_idx)
            
            if st.button("Update Statuses"):
                requires_amount = ["PROCESSING", "READY", "DELIVERED"]
                
                if new_status in requires_amount and (not order.total_amount or order.total_amount <= 0):
                    st.error("❌ You MUST enter and save the 'Total Amount' before moving to PROCESSING, READY, or DELIVERED.")
                elif order.status.name == "PENDING_PICKUP" and new_status not in ["PENDING_PICKUP", "CANCELLED", "REJECTED"] and not order.runner_id:
                    st.error("❌ You must Dispatch a Runner before you can progress the order status from PENDING_PICKUP.")
                elif new_status == "DELIVERED" and new_payment != "PAID":
                    st.error("❌ Cannot mark order as DELIVERED until payment is PAID.")
                else:
                    order.payment_status = getattr(PaymentStatus, new_payment)
                    order.status = getattr(OrderStatus, new_status)
                    
                    if new_payment == "PAID":
                        from app.models.schemas import PointTransaction
                        awarded = db.query(PointTransaction).filter(
                            PointTransaction.order_id == order.order_id,
                            PointTransaction.transaction_type == "EARNED"
                        ).first()
                        if not awarded:
                            from app.services.crud import add_points_transaction
                            points_earned = order.item_count * 2
                            add_points_transaction(db, order.customer_id, points_earned, "EARNED", order.order_id)
                            
                    db.commit()
                    
                    # If moved to IN_SHOP from PENDING_PICKUP, notify user
                    if new_status == "IN_SHOP" and order.customer and order.order_type.name == "PICKUP":
                        send_text_message(order.customer.phone_number, f"Good news! Your clothes (Order #{order.order_id}) have reached our shop securely.")
                    # If moved to READY
                    elif new_status == "READY" and order.customer:
                        delivery_fee = getattr(order, "delivery_fee", 0.0)
                        points_redeemed = getattr(order, "points_redeemed", 0)
                        final_amount = (order.total_amount or 0.0) + delivery_fee - points_redeemed
                        
                        if order.order_type.name == "PICKUP" and order.total_amount:
                            if delivery_fee == 0.0:
                                amount_text = f"Total bill is ₹{final_amount} (Delivery Fee Waived!)."
                            else:
                                amount_text = f"Total bill is ₹{final_amount} (Includes ₹{delivery_fee} Delivery Charge)."
                        elif order.total_amount:
                            amount_text = f"Total bill is ₹{final_amount}."
                        else:
                            amount_text = ""
                        send_text_message(order.customer.phone_number, f"Your clothes for Order #{order.order_id} are ready! {amount_text}\nWe will deliver them soon")
                    
                    st.success("Statuses updated successfully.")
                    st.rerun()
                
        with col3:
            # Runner Dispatch
            st.markdown("**Dispatch Delivery Runner**")
            
            runners = get_runners(db)
            if not runners:
                st.warning("No runners saved. Please add a runner in the sidebar.")
            else:
                runner_options = {f"{r.name} ({r.phone_number})": r.phone_number for r in runners}
                selected_runner_label = st.selectbox("Select Runner", list(runner_options.keys()))
                runner_phone = runner_options[selected_runner_label]
                
                if st.button("Dispatch Runner"):
                    customer_phone = order.customer.phone_number if order.customer else "N/A"
                    customer_name = order.customer.name if order.customer and order.customer.name else "Unknown"
                    location = order.customer.last_location_gps if order.customer and order.customer.last_location_gps else "No Location Provided"
                    
                    if location != "No Location Provided":
                        maps_link = f"https://www.google.com/maps?q={location}"
                    else:
                        maps_link = "No link available."
                        
                    action = 'PICKUP' if order.status.name == 'PENDING_PICKUP' else 'DELIVERY'
                    
                    if action == 'PICKUP':
                        est_raw = order.estimated_amount or 0.0
                        delivery_fee = getattr(order, "delivery_fee", 0.0)
                        points_redeemed = getattr(order, "points_redeemed", 0)
                        est_final = est_raw + delivery_fee - points_redeemed
                        amount_display = f"TBD (Estimate: ₹{est_final})"
                    else:
                        delivery_fee = getattr(order, "delivery_fee", 0.0)
                        points_redeemed = getattr(order, "points_redeemed", 0)
                        final_total = (order.total_amount or 0.0) + delivery_fee - points_redeemed
                        amount_display = f"₹{final_total}"
                    
                    dispatch_msg = (
                        f"🚨 *NEW DISPATCH: {order.order_id}* 🚨\n\n"
                        f"Action: {action}\n"
                        f"Service: {order.service_category or 'Dry Clean'}\n"
                        f"Customer: {customer_name} ({customer_phone})\n"
                        f"Items: {order.item_count}\n"
                        f"Instructions: {order.special_instructions or 'None'}\n"
                        f"Flat Address: {order.flat_address or 'N/A'}\n"
                        f"Location: {maps_link}\n"
                        f"Amount to Collect: {amount_display}"
                    )
                    
                    response = send_text_message(runner_phone, dispatch_msg)
                    if response.get("status") == "mocked" or "error" not in response:
                        # Record that a runner was dispatched so status progression is unlocked
                        if not order.runner_id:
                            order.runner_id = next(r.runner_id for r in runners if r.phone_number == runner_phone)
                            db.commit()
                        st.success(f"Dispatch message sent to {selected_runner_label}!")
                    else:
                        st.error("Failed to send WhatsApp message. Check API credentials.")
                        
        st.markdown("---")
        st.markdown("**⚠️ Danger Zone**")
        col_rj, col_cn, _ = st.columns([1, 1, 2])
        
        with col_rj:
            if st.button("Reject (Outside Paldi)"):
                order.status = getattr(OrderStatus, "REJECTED")
                db.commit()
                if order.customer:
                    send_text_message(order.customer.phone_number, f"We are sorry, but we currently only offer pickup and delivery within the Paldi area. Your pickup request (Order #{order.order_id}) has been rejected. However, you are always welcome to drop off your clothes at our shop!")
                st.success("Order Rejected.")
                st.rerun()
                
        with col_cn:
            if st.button("Cancel Order"):
                order.status = getattr(OrderStatus, "CANCELLED")
                db.commit()
                if order.customer:
                    send_text_message(order.customer.phone_number, f"Your pickup request (Order #{order.order_id}) has been cancelled.")
                st.success("Order Cancelled.")
                st.rerun()

with tab2:
    st.header("👥 Customer Database")
    st.markdown("View all registered customers and edit their saved pickup addresses.")
    
    customers = db.query(Customer).all()
    if not customers:
        st.info("No customers found.")
    else:
        cust_data = []
        for c in customers:
            cust_data.append({
                "Customer ID": c.customer_id,
                "Name": c.name or "Unknown",
                "Phone": c.phone_number,
                "Saved Address": c.saved_address or "",
                "GPS Location": c.last_location_gps or "",
                "Available Points": get_available_points(db, c.customer_id),
                "Order Count": c.order_count
            })
            
        cust_df = pd.DataFrame(cust_data)
        
        # We use data_editor to allow editing the 'Saved Address' and 'GPS Location' columns directly
        edited_df = st.data_editor(
            cust_df,
            column_config={
                "Customer ID": st.column_config.NumberColumn("ID", disabled=True),
                "Name": st.column_config.TextColumn("Name", disabled=True),
                "Phone": st.column_config.TextColumn("Phone", disabled=True),
                "Saved Address": st.column_config.TextColumn("Saved Address"),
                "GPS Location": st.column_config.TextColumn("GPS Location"),
                "Available Points": st.column_config.NumberColumn("Points", disabled=True),
                "Order Count": st.column_config.NumberColumn("Orders", disabled=True),
            },
            hide_index=True,
            use_container_width=True,
            key="customer_editor"
        )
        
        if st.button("Save Changes"):
            # Compare edited_df with cust_df to find changes
            changes_made = False
            for index, row in edited_df.iterrows():
                orig_address = cust_df.loc[index, "Saved Address"]
                new_address = row["Saved Address"]
                orig_gps = cust_df.loc[index, "GPS Location"]
                new_gps = row["GPS Location"]
                
                c_id = row["Customer ID"]
                db_cust = None
                
                if orig_address != new_address:
                    db_cust = db.query(Customer).filter(Customer.customer_id == c_id).first()
                    if db_cust:
                        db_cust.saved_address = new_address
                        changes_made = True
                        
                if orig_gps != new_gps:
                    if not db_cust:
                        db_cust = db.query(Customer).filter(Customer.customer_id == c_id).first()
                    if db_cust:
                        db_cust.last_location_gps = new_gps
                        changes_made = True
            
            if changes_made:
                db.commit()
                st.success("Customer data updated successfully!")
                st.rerun()

with tab3:
    st.header("🛵 Manage Delivery Staff")
    st.markdown("Add runners who will receive dispatch notifications.")
    with st.form("runner_entry_form"):
        r_name = st.text_input("Runner Name")
        r_phone = st.text_input("Runner WhatsApp Phone")
        r_submit = st.form_submit_button("Save Runner")
        if r_submit:
            if r_name and r_phone:
                from app.services.crud import create_runner
                create_runner(db, r_name, r_phone)
                st.success(f"Runner {r_name} saved!")
            else:
                st.error("Name and Phone required.")

db.close()
