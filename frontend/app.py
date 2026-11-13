import streamlit as st
import requests

# Updated to match the new Uvicorn port
API_URL = "http://localhost:8001"

# --- Helper Functions ---
def get_headers():
    if st.session_state.get("token"):
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}

def get_error_msg(res: requests.Response, default: str = "An error occurred") -> str:
    """Safely extract error messages to prevent JSONDecodeError on 500/404 pages."""
    try:
        return res.json().get("detail", default)
    except Exception:
        return f"HTTP {res.status_code}: {res.text}"

# --- Session State Initialization ---
if "token" not in st.session_state:
    st.session_state.token = None
if "username" not in st.session_state:
    st.session_state.username = None

# --- Sidebar (Authentication & Navigation) ---
page = "Feed"
with st.sidebar:
    if st.session_state.token is None:
        st.header("Authentication")
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            l_user = st.text_input("Username", key="l_user")
            l_pass = st.text_input("Password", type="password", key="l_pass")
            if st.button("Login"):
                res = requests.post(f"{API_URL}/login", json={"username": l_user, "password": l_pass})
                if res.status_code == 200:
                    try:
                        data = res.json()
                        st.session_state.token = data["access_token"]
                        st.session_state.username = data["username"]
                        st.rerun()
                    except Exception:
                        st.error("Login succeeded, but failed to parse server response.")
                else:
                    st.error(get_error_msg(res, "Login failed"))
                    
        with tab2:
            r_user = st.text_input("Username", key="r_user")
            r_pass = st.text_input("Password", type="password", key="r_pass")
            if st.button("Register"):
                res = requests.post(f"{API_URL}/register", json={"username": r_user, "password": r_pass})
                if res.status_code == 200:
                    st.success("Registered successfully! You can now log in.")
                else:
                    st.error(get_error_msg(res, "Registration failed"))
    else:
        st.write(f"Logged in as **{st.session_state.username}**")
        if st.button("Logout"):
            st.session_state.token = None
            st.session_state.username = None
            st.rerun()
            
        st.divider()
        page = st.radio("Navigation", ["Feed", "Debate Simulator"])

# --- Main App Area ---

if page == "Feed":
    st.title("Twitter Clone Feed")
    
    # Create Tweet Form
    if st.session_state.token:
        with st.form("new_tweet_form", clear_on_submit=True):
            tweet_content = st.text_area("What's happening?", max_chars=280)
            if st.form_submit_button("Post Tweet"):
                if tweet_content.strip():
                    res = requests.post(
                        f"{API_URL}/tweets", 
                        json={"content": tweet_content}, 
                        headers=get_headers()
                    )
                    if res.status_code == 200:
                        st.success("Tweet posted!")
                        st.rerun()
                    else:
                        st.error(get_error_msg(res, "Failed to post tweet"))

    st.divider()

    # Fetch and Display Tweets
    try:
        res = requests.get(f"{API_URL}/tweets", headers=get_headers())
        if res.status_code == 200:
            tweets = res.json()
            if not tweets:
                st.info("No tweets yet. Be the first to post!")
                
            for t in tweets:
                with st.container():
                    # Formatted timestamp mapping 2026-11-06T12:00:00 -> 2026-11-06 12:00
                    date_str = t['created_at'].replace('T', ' ')[:16]
                    st.markdown(f"**@{t['username']}** · _{date_str}_")
                    st.write(t['content'])
                    
                    # Like Button
                    liked = t.get('liked_by_me', False)
                    btn_label = "❤️ Unlike" if liked else "🤍 Like"
                    
                    if st.button(f"{btn_label} ({t['likes']})", key=f"like_{t['id']}"):
                        if st.session_state.token:
                            like_res = requests.post(f"{API_URL}/tweets/{t['id']}/like", headers=get_headers())
                            if like_res.status_code == 200:
                                st.rerun()
                            else:
                                st.error(get_error_msg(like_res, "Failed to like tweet"))
                        else:
                            st.warning("You must be logged in to like tweets.")

                    # Comments Section
                    with st.expander("Comments"):
                        c_res = requests.get(f"{API_URL}/tweets/{t['id']}/comments")
                        if c_res.status_code == 200:
                            comments = c_res.json()
                            if not comments:
                                st.caption("No comments yet.")
                            for c in comments:
                                st.markdown(f"**@{c['username']}**: {c['content']}")
                        
                        if st.session_state.token:
                            # Streamlit struggles with forms inside loops, so we use a text input and a button
                            col1, col2 = st.columns([4, 1])
                            with col1:
                                c_content = st.text_input("Add a comment...", key=f"c_input_{t['id']}")
                            with col2:
                                # Align button with text input
                                st.markdown("<br>", unsafe_allow_html=True) 
                                if st.button("Reply", key=f"c_btn_{t['id']}"):
                                    if c_content.strip():
                                        reply_res = requests.post(
                                            f"{API_URL}/tweets/{t['id']}/comments", 
                                            json={"content": c_content}, 
                                            headers=get_headers()
                                        )
                                        if reply_res.status_code == 200:
                                            st.rerun()
                                        else:
                                            st.error(get_error_msg(reply_res, "Failed to post comment"))
                st.divider()
        else:
            st.error(get_error_msg(res, "Failed to load feed from backend."))
    except requests.exceptions.ConnectionError:
        st.error("Failed to connect to the backend. Is Uvicorn running on port 8001?")

elif page == "Debate Simulator":
    st.title("AI Debate Simulator")
    st.write("Enter a topic to watch the AI agents debate it out.")
    
    topic = st.text_input("Debate Topic", placeholder="e.g., Is Python better than JavaScript?")
    turns = st.number_input("Maximum Turns", min_value=1, max_value=10, value=4)
    
    if st.button("Run Debate", type="primary"):
        if topic.strip():
            with st.spinner("Debating..."):
                try:
                    res = requests.post(f"{API_URL}/debate", json={"topic": topic, "max_turns": turns})
                    if res.status_code == 200:
                        st.json(res.json())
                    else:
                        st.error(get_error_msg(res, "Debate failed"))
                except Exception as e:
                    st.error(f"Connection error: {e}")
        else:
            st.warning("Please enter a topic.")