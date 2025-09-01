import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from collections import Counter
import re
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import time
import random
import pytz

st.set_page_config(page_title="IGN Forum Analyzer", layout="wide")

class IGNForumAnalyzer:
    def __init__(self, base_url="https://www.ignboards.com/forums/the-vestibule.5296/"):
        self.base_url = base_url
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        self.posts_data = []

    def _convert_abbreviated_number(self, text):
        """Convert abbreviated numbers (e.g., '32K', '1.5M') to integers"""
        text = text.strip().upper()
        multipliers = {
            'K': 1000,
            'M': 1000000,
            'B': 1000000000
        }
        
        text = text.replace(',', '')
        
        for suffix, multiplier in multipliers.items():
            if text.endswith(suffix):
                try:
                    number = float(text[:-1]) * multiplier
                    return int(number)
                except ValueError:
                    return 0
        
        try:
            return int(text)
        except ValueError:
            return 0

    def fetch_page(self, page_num=1):
        """Fetch a single page of forum posts"""
        try:
            time.sleep(random.uniform(0.5, 1.0))  # Simple rate limiting
            url = f"{self.base_url}page-{page_num}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            st.error(f"Error fetching page {page_num}: {e}")
            return None

    def extract_post_data(self, soup):
        """Extract relevant data from posts on a page"""
        threads = soup.find_all('div', class_='structItem--thread')
        
        for thread in threads:
            try:
                title = thread.find('div', class_='structItem-title').text.strip()
                
                author_elem = thread.find('a', class_='username')
                author = author_elem.text.strip() if author_elem else "Unknown"
                
                timestamp_elem = thread.find('time')
                
                if timestamp_elem and timestamp_elem.get('datetime'):
                    timestamp = pd.to_datetime(timestamp_elem['datetime']).tz_convert(pytz.UTC)
                    
                    stats_elem = thread.find('div', class_='structItem-cell--meta')
                    replies = 0
                    views = 0
                    
                    if stats_elem:
                        dl_elements = stats_elem.find_all('dl')
                        
                        for dl in dl_elements:
                            dt = dl.find('dt')
                            dd = dl.find('dd')
                            if dt and dd:
                                if 'Replies' in dt.text:
                                    replies = self._convert_abbreviated_number(dd.text)
                                elif 'Views' in dt.text:
                                    views = self._convert_abbreviated_number(dd.text)
                    
                    self.posts_data.append({
                        'title': title,
                        'author': author,
                        'timestamp': timestamp,
                        'replies': replies,
                        'views': views
                    })
            except Exception as e:
                st.warning(f"Error extracting post data: {e}")

    def scrape_pages(self, num_pages):
        """Scrape specified number of pages"""
        self.posts_data = []  # Reset data
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for page in range(1, num_pages + 1):
            status_text.text(f"Scraping page {page}/{num_pages}...")
            soup = self.fetch_page(page)
            if soup:
                self.extract_post_data(soup)
            progress_bar.progress(page / num_pages)
        
        status_text.text("Scraping complete!")
        return pd.DataFrame(self.posts_data)

@st.cache_data
def scrape_forum_data(num_pages):
    """Cached function to scrape forum data"""
    analyzer = IGNForumAnalyzer()
    return analyzer.scrape_pages(num_pages)

def filter_by_date_range(df, days_back=2):
    """Filter dataframe to include only threads from the last N full calendar days"""
    if df.empty:
        return df
    
    # Get current date in UTC
    today = datetime.now(pytz.UTC).date()
    
    # Calculate the start date (N days back)
    start_date = today - timedelta(days=days_back)
    
    # Convert timestamps to dates for comparison
    df['date'] = df['timestamp'].dt.date
    
    # Filter for the last N calendar days
    filtered_df = df[df['date'] >= start_date].copy()
    
    return filtered_df

def create_visualizations(df):
    """Create all visualizations"""
    if df.empty:
        st.warning("No data to visualize")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Dataset Overview")
        st.metric("Total Threads", len(df))
        st.metric("Unique Authors", df['author'].nunique())
        st.metric("Total Replies", int(df['replies'].sum()))
        st.metric("Total Views", int(df['views'].sum()))
    
    with col2:
        st.subheader("📅 Date Range")
        if not df.empty:
            min_date = df['timestamp'].min().strftime('%Y-%m-%d')
            max_date = df['timestamp'].max().strftime('%Y-%m-%d')
            st.write(f"From: {min_date}")
            st.write(f"To: {max_date}")
    
    # Top threads by replies table
    st.subheader("🔥 Top Threads by Replies")
    top_threads = df.nlargest(20, 'replies')[['title', 'author', 'replies', 'views', 'timestamp']]
    top_threads['timestamp'] = top_threads['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
    st.dataframe(top_threads, use_container_width=True)
    
    # Authors with most total replies on their threads
    st.subheader("👑 Authors by Total Replies on Their Threads")
    author_replies = df.groupby('author')['replies'].sum().reset_index()
    author_replies = author_replies.sort_values('replies', ascending=False).head(15)
    
    fig_replies = px.bar(
        author_replies, 
        x='author', 
        y='replies',
        title="Authors with Most Total Replies on Their Threads",
        labels={'author': 'Author', 'replies': 'Total Replies'}
    )
    fig_replies.update_xaxes(tickangle=45)
    st.plotly_chart(fig_replies, use_container_width=True)
    
    # Authors with most total views on their threads
    st.subheader("👀 Authors by Total Views on Their Threads")
    author_views = df.groupby('author')['views'].sum().reset_index()
    author_views = author_views.sort_values('views', ascending=False).head(15)
    
    fig_views = px.bar(
        author_views, 
        x='author', 
        y='views',
        title="Authors with Most Total Views on Their Threads",
        labels={'author': 'Author', 'views': 'Total Views'}
    )
    fig_views.update_xaxes(tickangle=45)
    st.plotly_chart(fig_views, use_container_width=True)

def main():
    st.title("🎮 IGN Forum Analyzer")
    st.write("Analyze recent activity on IGN's The Vestibule forum")
    
    # Sidebar controls
    st.sidebar.header("⚙️ Settings")
    
    # Page limit input
    num_pages = st.sidebar.number_input(
        "Number of pages to scrape", 
        min_value=1, 
        max_value=50, 
        value=5,
        help="Number of forum pages to scrape (more pages = longer scraping time)"
    )
    
    # Days back filter
    days_back = st.sidebar.number_input(
        "Filter to last N calendar days", 
        min_value=1, 
        max_value=30, 
        value=2,
        help="Show only threads created in the last N full calendar days"
    )
    
    # Scrape button
    if st.sidebar.button("🚀 Start Scraping", type="primary"):
        st.info(f"Scraping {num_pages} pages from IGN Forum...")
        
        # Scrape data
        with st.spinner("Scraping forum data..."):
            raw_df = scrape_forum_data(num_pages)
        
        if not raw_df.empty:
            st.success(f"Successfully scraped {len(raw_df)} threads!")
            
            # Filter by date range
            filtered_df = filter_by_date_range(raw_df, days_back)
            
            if not filtered_df.empty:
                st.success(f"Found {len(filtered_df)} threads in the last {days_back} calendar days")
                
                # Store in session state
                st.session_state.df = filtered_df
                st.session_state.raw_df = raw_df
                
            else:
                st.warning(f"No threads found in the last {days_back} calendar days. Showing all scraped data instead.")
                st.session_state.df = raw_df
                st.session_state.raw_df = raw_df
        else:
            st.error("No data was scraped. Please try again.")
    
    # Display results if data exists
    if 'df' in st.session_state and not st.session_state.df.empty:
        st.header("📈 Analysis Results")
        create_visualizations(st.session_state.df)
        
        # Download option
        st.subheader("💾 Download Data")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Download Filtered Data as CSV"):
                csv = st.session_state.df.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name=f"ign_forum_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        
        with col2:
            if st.button("Download All Scraped Data as CSV"):
                csv = st.session_state.raw_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download All Data CSV",
                    data=csv,
                    file_name=f"ign_forum_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
    
    # Instructions
    if 'df' not in st.session_state:
        st.info("👈 Use the sidebar to configure settings and start scraping!")
        
        st.subheader("ℹ️ How it works:")
        st.write("""
        1. **Set the number of pages** to scrape (default: 5)
        2. **Set the date filter** to show threads from the last N calendar days (default: 2)
        3. **Click 'Start Scraping'** to begin collecting data
        4. **View the results** including top threads, author statistics, and visualizations
        5. **Download the data** as CSV if needed
        
        The app will scrape the most recent pages from IGN's The Vestibule forum and filter the results to show only threads created within your specified date range.
        """)

if __name__ == "__main__":
    main()
