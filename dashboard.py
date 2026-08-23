import streamlit as st
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()

# We can import directly from our app modules since dashboard.py is at the root
from app.core.database import SessionLocal
from app.models.schemas import Order, OrderStatus, PaymentStatus, Customer, OrderType, Runner, OrderItem, CatalogItem
from app.services.whatsapp_sender import send_text_message
from app.services.crud import create_customer, create_order, get_customer, get_runners, create_runner, update_customer_name, get_available_points, get_monthly_order_count

def format_wa_phone(phone: str) -> str:
    # Strip all non-digit characters
    digits = "".join([c for c in phone if c.isdigit()])
    # If it is exactly 10 digits, prefix it with Indian country code '91'
    if len(digits) == 10:
        return f"91{digits}"
    # If it is 12 digits starting with '91', return it
    if len(digits) == 12 and digits.startswith("91"):
        return digits
    return digits

import hashlib

st.set_page_config(page_title="Ashirwad Cleaners Admin", layout="wide")

def get_expected_token() -> str:
    env_user = os.getenv("ADMIN_USERNAME", "admin")
    env_pass = os.getenv("ADMIN_PASSWORD", "ashirwad123")
    return hashlib.sha256(f"{env_user}:{env_pass}".encode()).hexdigest()

# Persistent session recovery via URL query params
expected_token = get_expected_token()
if "auth" in st.query_params and st.query_params["auth"] == expected_token:
    st.session_state.logged_in = True

# ----- ADMIN AUTHENTICATION SECURITY -----
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

def check_login():
    username = st.session_state.login_username
    password = st.session_state.login_password
    
    env_user = os.getenv("ADMIN_USERNAME", "admin")
    env_pass = os.getenv("ADMIN_PASSWORD", "ashirwad123")
    
    if username == env_user and password == env_pass:
        st.session_state.logged_in = True
        st.session_state.login_error = False
        st.query_params["auth"] = expected_token
    else:
        st.session_state.logged_in = False
        st.session_state.login_error = True

if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("## 🧺 Ashirwad Cleaners: Admin Login")
        st.markdown("Please enter your administrator credentials to access the live dashboard.")
        
        st.text_input("Username", key="login_username")
        st.text_input("Password", type="password", key="login_password")
        
        if st.session_state.get("login_error"):
            st.error("❌ Incorrect username or password. Please try again.")
            
        st.button("Log In", on_click=check_login, use_container_width=True)
    st.stop()

# Sidebar for logout controls
with st.sidebar:
    st.markdown("### 🧺 Session Control")
    if st.button("🚪 Log Out", use_container_width=True):
        st.query_params.clear()
        st.session_state.logged_in = False
        st.rerun()

col_title, col_ref = st.columns([4, 1])
with col_title:
    st.title("🧺 Ashirwad Cleaners: Admin Dashboard")
with col_ref:
    st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

# JS Injector to trigger the refresh button click silently every 15 seconds
import streamlit.components.v1 as components
components.html(
    """
    <script>
        const clickRefresh = () => {
            const doc = window.parent.document;
            const buttons = Array.from(doc.querySelectorAll('button'));
            const refreshBtn = buttons.find(el => el.innerText && el.innerText.includes('Refresh Data'));
            if (refreshBtn) {
                refreshBtn.click();
            }
        };
        // Trigger auto-refresh every 15 seconds
        setInterval(clickRefresh, 15000);
    </script>
    """,
    height=0
)

def format_ist_datetime(dt) -> str:
    if not dt:
        return "N/A"
    return dt.strftime("%d %b %Y, %I:%M %p")

STATUS_HUMAN_MAP = {
    "PENDING_PICKUP": "Pending Pickup",
    "PICKED_UP": "Picked Up",
    "IN_SHOP": "Received at Shop",
    "PROCESSING": "In Cleaning & Processing",
    "READY": "Ready for Delivery",
    "OUT_FOR_DELIVERY": "Out for Delivery",
    "DELIVERED": "Delivered",
    "CANCELLED": "Cancelled",
    "REJECTED": "Rejected"
}

ORDER_TYPE_HUMAN_MAP = {
    "PICKUP": "Pickup & Delivery",
    "STORE_DROP": "Store Drop-off"
}

PAYMENT_STATUS_HUMAN_MAP = {
    "UNPAID": "Unpaid",
    "PAID": "Paid"
}

with SessionLocal() as db:
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

    # ----- TABS -----
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Active Orders", "👥 Customer Database", "⚙️ Staff Settings", "🏷️ Price Catalog Manager"])

    def load_active_orders(db_session, show_all=False):
        if show_all:
            orders = db_session.query(Order).all()
        else:
            orders = db_session.query(Order).filter(~Order.status.in_([OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.REJECTED])).all()
        
        data = []
        for o in orders:
            delivery_fee = getattr(o, "delivery_fee", 0.0)
            raw_est = o.estimated_amount or 0.0
            raw_total = o.total_amount or 0.0
            
            order_type_str = ORDER_TYPE_HUMAN_MAP.get(o.order_type.name, o.order_type.name.replace("_", " ").title())
            payment_str = PAYMENT_STATUS_HUMAN_MAP.get(o.payment_status.name, o.payment_status.name.replace("_", " ").title())
            status_str = STATUS_HUMAN_MAP.get(o.status.name, o.status.name.replace("_", " ").title())

            data.append({
                "Order ID": o.order_id,
                "Order Date & Time": format_ist_datetime(o.created_at),
                "Picked Up At": format_ist_datetime(o.picked_up_at),
                "Delivered At": format_ist_datetime(o.delivered_at),
                "Type": order_type_str,
                "Service(s)": o.service_category or "Dry Clean",
                "Customer Name": o.customer.name if o.customer and o.customer.name else "Unknown",
                "Customer Phone": o.customer.phone_number if o.customer else "Unknown",
                "Text Address": o.flat_address or "N/A",
                "GPS Location": o.customer.last_location_gps if o.customer and o.customer.last_location_gps else "N/A",
                "Items": o.item_count,
                "Final Total": f"₹{raw_total + delivery_fee - o.points_redeemed}" if o.total_amount else f"₹{raw_est + delivery_fee - o.points_redeemed}",
                "Payment": payment_str,
                "Status": status_str
            })
        return pd.DataFrame(data), orders

    with tab1:
        show_all = st.checkbox("Show all orders (including delivered)", value=False)
        df, raw_orders = load_active_orders(db, show_all)
    
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
                st.markdown(f"**📅 Order Date & Time:** {format_ist_datetime(order.created_at)}")
                if order.picked_up_at:
                    st.markdown(f"**🚚 Picked Up At:** {format_ist_datetime(order.picked_up_at)}")
                if order.delivered_at:
                    st.markdown(f"**✅ Delivered At:** {format_ist_datetime(order.delivered_at)}")
                st.markdown(f"**Services Requested:** {order.service_category}")
                st.markdown(f"**Pickup Address:** {order.flat_address}")
                
                if order.items:
                    st.markdown("**Itemized Garments:**")
                    for oi in order.items:
                        serv_display = oi.service_type.replace("_", " ").title() if oi.service_type else "Dry Clean"
                        st.markdown(f"- {oi.quantity}x {oi.garment_type} ({serv_display})")
                else:
                    st.markdown("*(No itemized breakdown available for this order)*")
                    
            with st.expander("✏️ Edit Order Items & Address"):
                new_address = st.text_input("Address", value=order.flat_address or "")
                new_instructions = st.text_area("Special Instructions", value=order.special_instructions or "")
                
                st.markdown("##### Garments Breakdown")
                
                # Fetch all catalog items to populate dropdown options
                catalog_items = db.query(CatalogItem).all()
                all_garments = sorted(list(set([item.item_name for item in catalog_items])))
                if not all_garments:
                    all_garments = ["Shirt", "Pant", "Saree", "Suit", "Blanket"] # Fallback if empty
                
                # Keep trace of current items in session state so user can add/delete rows dynamically
                session_key = f"items_{order.order_id}"
                if session_key not in st.session_state:
                    st.session_state[session_key] = [
                        {
                            "garment_type": oi.garment_type,
                            "service_type": oi.service_type,
                            "quantity": oi.quantity
                        }
                        for oi in order.items
                    ]
                
                current_items = st.session_state[session_key]
                
                updated_items = []
                for idx, item in enumerate(current_items):
                    col_s, col_g, col_q, col_d = st.columns([3, 3, 2, 1])
                    with col_s:
                        services_list = ["Dry Clean", "Washing", "Steam Press", "Petrol Wash"]
                        display_service_map = {
                            "dry_clean": "Dry Clean",
                            "washing": "Washing",
                            "steam_press": "Steam Press",
                            "petrol_wash": "Petrol Wash"
                        }
                        code_service_map = {v: k for k, v in display_service_map.items()}
                        current_disp = display_service_map.get(item["service_type"], "Dry Clean")
                        s_idx = services_list.index(current_disp) if current_disp in services_list else 0
                        s_disp = st.selectbox(f"Service #{idx+1}", services_list, index=s_idx, key=f"s_{order.order_id}_{idx}")
                        s_type = code_service_map[s_disp]
                        
                    with col_g:
                        # Filter garments by the selected service category
                        service_garments = sorted(list(set([c_item.item_name for c_item in catalog_items if c_item.service_type == s_type])))
                        if not service_garments:
                            service_garments = ["No items in this category"]
                            g_type = service_garments[0]
                            st.selectbox(f"Garment #{idx+1}", service_garments, index=0, disabled=True, key=f"g_{order.order_id}_{idx}")
                        else:
                            g_idx = service_garments.index(item["garment_type"]) if item["garment_type"] in service_garments else 0
                            g_type = st.selectbox(f"Garment #{idx+1}", service_garments, index=g_idx, key=f"g_{order.order_id}_{idx}")
                            
                    with col_q:
                        qty = st.number_input(f"Qty #{idx+1}", min_value=1, value=int(item["quantity"]), key=f"q_{order.order_id}_{idx}")
                    with col_d:
                        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                        delete_row = st.checkbox("🗑️", key=f"del_{order.order_id}_{idx}")
                    
                    if not delete_row and g_type != "No items in this category":
                        updated_items.append({
                            "garment_type": g_type,
                            "service_type": s_type,
                            "quantity": qty
                        })
                
                col_add, col_save = st.columns(2)
                with col_add:
                    if st.button("➕ Add Item Row"):
                        default_service = "dry_clean"
                        default_garments = sorted(list(set([c_item.item_name for c_item in catalog_items if c_item.service_type == default_service])))
                        if not default_garments:
                            for s_key in ["washing", "steam_press", "petrol_wash"]:
                                default_garments = sorted(list(set([c_item.item_name for c_item in catalog_items if c_item.service_type == s_key])))
                                if default_garments:
                                    default_service = s_key
                                    break
                        current_items.append({
                            "garment_type": default_garments[0] if default_garments else "Shirt",
                            "service_type": default_service,
                            "quantity": 1
                        })
                        st.session_state[session_key] = current_items
                        st.rerun()
                with col_save:
                    if st.button("💾 Save Order Changes"):
                        order.flat_address = new_address
                        order.special_instructions = new_instructions
                        
                        db.query(OrderItem).filter(OrderItem.order_id == order.order_id).delete()
                        
                        total_qty = 0
                        estimated_sum = 0.0
                        services_used = set()
                        
                        price_lookup = {}
                        for c_item in catalog_items:
                            price_lookup[(c_item.service_type, c_item.item_name)] = c_item.price
                        
                        for u_item in updated_items:
                            oi = OrderItem(
                                order_id=order.order_id,
                                garment_type=u_item["garment_type"],
                                service_type=u_item["service_type"],
                                quantity=u_item["quantity"]
                            )
                            db.add(oi)
                            
                            total_qty += u_item["quantity"]
                            services_used.add(u_item["service_type"].replace("_", " ").title())
                            
                            item_price = price_lookup.get((u_item["service_type"], u_item["garment_type"]), 50.0)
                            estimated_sum += (item_price * u_item["quantity"])
                        
                        order.item_count = total_qty
                        order.estimated_amount = estimated_sum
                        order.service_category = ", ".join(list(services_used)) if services_used else "Dry Clean"
                        
                        # Recalculate Delivery Fee
                        monthly_orders = get_monthly_order_count(db, order.customer_id)
                        if monthly_orders >= 4:
                            order.delivery_fee = 0.0
                        else:
                            order.delivery_fee = 30.0
                        
                        db.commit()
                        if session_key in st.session_state:
                            del st.session_state[session_key]
                        st.success("Order changes saved successfully!")
                        st.rerun()
                        
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Update Price
                st.markdown("**Update Final Price**")
                
                raw_val = float(order.total_amount or order.estimated_amount or 0.0)
                delivery_fee = getattr(order, "delivery_fee", 0.0)
                points_redeemed = getattr(order, "points_redeemed", 0)
                
                st.markdown(f"*(Raw Estimate was: ₹{order.estimated_amount or 0.0})*")
                new_raw_price = st.number_input("Raw Clothes Amount (₹)", min_value=0.0, value=raw_val, step=10.0, key=f"raw_price_{order.order_id}")
                
                st.markdown(f"**+ Delivery Fee:** ₹{delivery_fee}")
                if points_redeemed > 0:
                    st.markdown(f"**- Points Redeemed:** ₹{points_redeemed}")
                st.markdown(f"**= Final Total to Collect:** ₹{new_raw_price + delivery_fee - points_redeemed}")
                
                if st.button("Save Price", key=f"btn_save_price_{order.order_id}"):
                    order.total_amount = new_raw_price
                    db.commit()
                    st.success(f"Raw Price saved as ₹{new_raw_price}")
                    st.rerun()
                    
            with col2:
                # Update Payment & Order Status
                st.markdown("**Update Status**")
                new_payment = st.selectbox("Payment Status", [p.name for p in PaymentStatus], index=[p.name for p in PaymentStatus].index(order.payment_status.name), format_func=lambda p: PAYMENT_STATUS_HUMAN_MAP.get(p, p.replace("_", " ").title()), key=f"pay_status_{order.order_id}")
                valid_statuses = [s.name for s in OrderStatus if s.name not in ["CANCELLED", "REJECTED"]]
                default_idx = valid_statuses.index(order.status.name) if order.status.name in valid_statuses else 0
                new_status = st.selectbox("Order Status", valid_statuses, index=default_idx, format_func=lambda s: STATUS_HUMAN_MAP.get(s, s.replace("_", " ").title()), key=f"ord_status_{order.order_id}")
                
                if st.button("Update Statuses", key=f"btn_update_status_{order.order_id}"):
                    requires_amount = ["PROCESSING", "READY", "DELIVERED"]
                    
                    if new_status in requires_amount and (not order.total_amount or order.total_amount <= 0):
                        st.error("❌ You MUST enter and save the 'Total Amount' before moving to PROCESSING, READY, or DELIVERED.")
                    elif order.status.name == "PENDING_PICKUP" and new_status not in ["PENDING_PICKUP", "CANCELLED", "REJECTED"] and not order.runner_id:
                        st.error("❌ You must Dispatch a Runner before you can progress the order status from PENDING_PICKUP.")
                    elif new_status == "DELIVERED" and new_payment != "PAID":
                        st.error("❌ Cannot mark order as DELIVERED until payment is PAID.")
                    else:
                        from app.services.crud import now_ist
                        order.payment_status = getattr(PaymentStatus, new_payment)
                        order.status = getattr(OrderStatus, new_status)
                        
                        if new_status in ["IN_SHOP", "PICKED_UP"] and not order.picked_up_at:
                            order.picked_up_at = now_ist()
                        if new_status == "DELIVERED" and not order.delivered_at:
                            order.delivered_at = now_ist()
                        
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
                        elif new_status == "DELIVERED" and order.customer:
                            dt_created = format_ist_datetime(order.created_at)
                            dt_del = format_ist_datetime(order.delivered_at)
                            send_text_message(
                                order.customer.phone_number,
                                f"🎉 *Order #{order.order_id} Delivered!* 🎉\n\n"
                                f"📅 *Order Placed*: {dt_created}\n"
                                f"🚚 *Delivered At*: {dt_del}\n\n"
                                f"Thank you for choosing Ashirwad Cleaners! We look forward to taking care of your garments again."
                            )
                        
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
                    selected_runner_label = st.selectbox("Select Runner", list(runner_options.keys()), key=f"sel_runner_{order.order_id}")
                    runner_phone = runner_options[selected_runner_label]
                    
                    if st.button("Dispatch Runner", key=f"btn_dispatch_{order.order_id}"):
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
                if st.button("Reject (Outside Paldi)", key=f"btn_reject_{order.order_id}"):
                    order.status = getattr(OrderStatus, "REJECTED")
                    db.commit()
                    if order.customer:
                        send_text_message(order.customer.phone_number, f"We are sorry, but we currently only offer pickup and delivery within the Paldi area. Your pickup request (Order #{order.order_id}) has been rejected. However, you are always welcome to drop off your clothes at our shop!")
                    st.success("Order Rejected.")
                    st.rerun()
                    
            with col_cn:
                if st.button("Cancel Order", key=f"btn_cancel_{order.order_id}"):
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
    st.markdown("View, edit, or add delivery staff runners.")
    
    # 1. Fetch and display existing runners in an editable grid
    runners = get_runners(db)
    if not runners:
        st.info("No runners currently registered.")
    else:
        st.subheader("Existing Staff Members")
        runner_data = []
        for r in runners:
            runner_data.append({
                "Runner ID": r.runner_id,
                "Name": r.name,
                "WhatsApp Phone": r.phone_number
            })
        runner_df = pd.DataFrame(runner_data)
        
        edited_runner_df = st.data_editor(
            runner_df,
            column_config={
                "Runner ID": st.column_config.NumberColumn("Runner ID", disabled=True),
                "Name": st.column_config.TextColumn("Runner Name"),
                "WhatsApp Phone": st.column_config.TextColumn("WhatsApp Phone")
            },
            hide_index=True,
            use_container_width=True,
            key="runner_editor"
        )
        
        col_r_save, _ = st.columns([1, 4])
        with col_r_save:
            if st.button("Save Staff Changes"):
                runner_changes = False
                for index, row in edited_runner_df.iterrows():
                    r_id = row["Runner ID"]
                    db_runner = db.query(Runner).filter(Runner.runner_id == r_id).first()
                    if db_runner:
                        formatted_phone = format_wa_phone(row["WhatsApp Phone"])
                        if db_runner.name != row["Name"]:
                            db_runner.name = row["Name"]
                            runner_changes = True
                        if db_runner.phone_number != formatted_phone:
                            db_runner.phone_number = formatted_phone
                            runner_changes = True
                
                if runner_changes:
                    db.commit()
                    st.success("Runner staff details updated successfully!")
                    st.rerun()
                    
        st.markdown("---")
        
        # Delete Runner option
        st.subheader("🗑️ Delete Staff Member")
        delete_options = {f"{r.name} ({r.phone_number})": r.runner_id for r in runners}
        runner_to_delete = st.selectbox("Select staff member to remove", list(delete_options.keys()))
        if st.button("Delete Staff Member"):
            del_runner_id = delete_options[runner_to_delete]
            db.query(Runner).filter(Runner.runner_id == del_runner_id).delete()
            db.commit()
            st.success("Successfully removed runner!")
            st.rerun()
            
        st.markdown("---")

    # 2. Form to Add a New Runner
    st.subheader("➕ Register New Staff Member")
    with st.form("runner_entry_form"):
        r_name = st.text_input("Runner Name")
        r_phone = st.text_input("Runner WhatsApp Phone (e.g. 9377718648)")
        r_submit = st.form_submit_button("Save Runner")
        if r_submit:
            if r_name and r_phone:
                formatted_phone = format_wa_phone(r_phone)
                from app.services.crud import create_runner
                create_runner(db, r_name, formatted_phone)
                st.success(f"Runner {r_name} saved!")
                st.rerun()
            else:
                st.error("Name and Phone required.")

with tab4:
    st.header("🏷️ Price Catalog Manager")
    st.markdown("Manage global services and garment base prices dynamically.")
    
    # 1. Selector for Category
    categories = {
        "Dry Clean": "dry_clean",
        "Washing": "washing",
        "Steam Press": "steam_press",
        "Petrol Wash": "petrol_wash"
    }
    selected_category_label = st.selectbox("Select Service Category to Manage", list(categories.keys()))
    service_key = categories[selected_category_label]
    
    # Query items for this category
    catalog_items = db.query(CatalogItem).filter(CatalogItem.service_type == service_key).all()
    
    # 2. Render editable grid
    if not catalog_items:
        st.info(f"No catalog items currently in '{selected_category_label}' category.")
        cat_df = pd.DataFrame(columns=["ID", "Garment Name", "Price (₹)", "Variable Price", "Note"])
    else:
        grid_data = []
        for item in catalog_items:
            grid_data.append({
                "ID": item.id,
                "Garment Name": item.item_name,
                "Price (₹)": float(item.price),
                "Variable Price": bool(item.is_variable),
                "Note": item.note or ""
            })
        cat_df = pd.DataFrame(grid_data)
        
    edited_cat_df = st.data_editor(
        cat_df,
        column_config={
            "ID": st.column_config.NumberColumn("ID", disabled=True),
            "Garment Name": st.column_config.TextColumn("Garment Name"),
            "Price (₹)": st.column_config.NumberColumn("Price (₹)"),
            "Variable Price": st.column_config.CheckboxColumn("Variable Price"),
            "Note": st.column_config.TextColumn("Note")
        },
        hide_index=True,
        use_container_width=True,
        key=f"catalog_editor_{service_key}"
    )
    
    # Save Grid edits
    col_g_save, _ = st.columns([1, 4])
    with col_g_save:
        if st.button("Save Grid Changes", key=f"save_grid_{service_key}"):
            grid_changes = False
            for index, row in edited_cat_df.iterrows():
                orig_row = cat_df.loc[index]
                item_id = row["ID"]
                db_item = db.query(CatalogItem).filter(CatalogItem.id == item_id).first()
                
                if db_item:
                    if db_item.item_name != row["Garment Name"]:
                        db_item.item_name = row["Garment Name"]
                        grid_changes = True
                    if db_item.price != row["Price (₹)"]:
                        db_item.price = row["Price (₹)"]
                        grid_changes = True
                    if db_item.is_variable != row["Variable Price"]:
                        db_item.is_variable = row["Variable Price"]
                        grid_changes = True
                    if db_item.note != row["Note"]:
                        db_item.note = row["Note"]
                        grid_changes = True
            
            if grid_changes:
                db.commit()
                st.success("Catalog grid changes saved successfully!")
                st.rerun()
                
    st.markdown("---")
    
    # 3. Form to Add a New Item to this category
    st.subheader(f"➕ Add New Garment to {selected_category_label}")
    with st.form(f"add_catalog_item_form_{service_key}"):
        col_name, col_price, col_var, col_note = st.columns([3, 2, 2, 4])
        with col_name:
            new_item_name = st.text_input("Garment Name (e.g. Saree, Suit, Coat)")
        with col_price:
            new_item_price = st.number_input("Base Price (₹)", min_value=0.0, value=50.0, step=5.0)
        with col_var:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            new_item_var = st.checkbox("Variable Price")
        with col_note:
            new_item_note = st.text_input("Special Notes / Price Range (e.g. Range 80-200 by size)")
            
        submitted = st.form_submit_button("Add Item to Catalog")
        if submitted:
            if not new_item_name:
                st.error("❌ Garment Name is required.")
            else:
                new_db_item = CatalogItem(
                    service_type=service_key,
                    item_name=new_item_name.strip(),
                    price=new_item_price,
                    is_variable=new_item_var,
                    note=new_item_note.strip() if new_item_note else None
                )
                db.add(new_db_item)
                db.commit()
                st.success(f"Successfully added '{new_item_name}' to '{selected_category_label}' catalog!")
                st.rerun()
                
    st.markdown("---")
    
    # 4. Remove Item from this category
    st.subheader(f"🗑️ Delete Garment from {selected_category_label}")
    if not catalog_items:
        st.info("No items to delete.")
    else:
        delete_options = {item.item_name: item.id for item in catalog_items}
        item_to_delete = st.selectbox("Select Garment to Delete", list(delete_options.keys()))
        if st.button("Delete Item from Catalog", key=f"del_cat_{service_key}"):
            del_id = delete_options[item_to_delete]
            db.query(CatalogItem).filter(CatalogItem.id == del_id).delete()
            db.commit()
            st.success(f"Successfully deleted '{item_to_delete}' from catalog!")
            st.rerun()

