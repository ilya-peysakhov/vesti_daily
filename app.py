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
from PIL import Image, ImageDraw, ImageFont
import io

st.set_page_config(page_title="IGN Forum 2025 Wrapped", layout="wide", initial_sidebar_state="expanded")

# Custom CSS for Wrapped-style design
st.markdown("""
<style>
    .wrapped-title {
        font-size: 4rem;
        font-weight: 900;
        text-align: center;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    .wrapped-subtitle {
        font-size: 1.5rem;
        text-align: center;
        color: #666;
        margin-bottom: 3rem;
    }
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        text-align: center;
        color: white;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    .stat-number {
        font-size: 3rem;
        font-weight: 900;
        margin: 0;
    }
    .stat-label {
        font-size: 1.2rem;
        opacity: 0.9;
        margin-top: 0.5rem;
    }
    .section-header {
        font-size: 2.5rem;
        font-weight: 800;
        margin: 3rem 0 1.5rem 0;
        text-align: center;
    }
    .emoji-large {
        font-size: 4rem;
        text-align: center;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

if st.sidebar.button('🔄 Clear Cache'):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()
    
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
            time.sleep(random.uniform(0.5, 1.0))
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
        self.posts_data = []
        
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

def filter_by_date(df, start_date, end_date):
    """Filter dataframe to include only threads from the specified date range"""
    if df.empty:
        return df
    
    df['date'] = df['timestamp'].dt.date
    filtered_df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].copy()
    
    return filtered_df

def create_infographic(filtered_df, start_date, end_date):
    """Create a shareable infographic image"""
    # Create image
    width, height = 1080, 1920
    img = Image.new('RGB', (width, height), color='#1a1a2e')
    draw = ImageDraw.Draw(img)
    
    # Try to use a nice font, fall back to default if not available
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
        header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 50)
        stat_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
        label_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
        body_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except:
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        stat_font = ImageFont.load_default()
        label_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
    
    y_position = 80
    
    # Title
    title = "2025 WRAPPED"
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    draw.text(((width - title_width) / 2, y_position), title, fill='#667eea', font=title_font)
    y_position += 100
    
    # Subtitle
    subtitle = f"IGN Forum: The Vestibule"
    subtitle_bbox = draw.textbbox((0, 0), subtitle, font=label_font)
    subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
    draw.text(((width - subtitle_width) / 2, y_position), subtitle, fill='#ffffff', font=label_font)
    y_position += 50
    
    date_range = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
    date_bbox = draw.textbbox((0, 0), date_range, font=label_font)
    date_width = date_bbox[2] - date_bbox[0]
    draw.text(((width - date_width) / 2, y_position), date_range, fill='#aaaaaa', font=label_font)
    y_position += 100
    
    # Stats section
    stats = [
        (f"{len(filtered_df):,}", "Threads Created", "🧵"),
        (f"{int(filtered_df['replies'].sum()):,}", "Total Replies", "💬"),
        (f"{int(filtered_df['views'].sum()):,}", "Total Views", "👀"),
        (f"{filtered_df['author'].nunique():,}", "Active Authors", "👥")
    ]
    
    stat_box_width = 480
    stat_box_height = 150
    padding = 30
    
    for i, (stat, label, emoji) in enumerate(stats):
        row = i // 2
        col = i % 2
        x = 60 + col * (stat_box_width + padding)
        y = y_position + row * (stat_box_height + padding)
        
        # Draw rounded rectangle
        draw.rounded_rectangle(
            [(x, y), (x + stat_box_width, y + stat_box_height)],
            radius=15,
            fill='#2d2d44'
        )
        
        # Draw emoji
        emoji_bbox = draw.textbbox((0, 0), emoji, font=header_font)
        emoji_width = emoji_bbox[2] - emoji_bbox[0]
        draw.text((x + (stat_box_width - emoji_width) / 2, y + 15), emoji, font=header_font)
        
        # Draw stat
        stat_bbox = draw.textbbox((0, 0), stat, font=stat_font)
        stat_width = stat_bbox[2] - stat_bbox[0]
        draw.text((x + (stat_box_width - stat_width) / 2, y + 60), stat, fill='#ffffff', font=stat_font)
        
        # Draw label
        label_bbox = draw.textbbox((0, 0), label, font=label_font)
        label_width = label_bbox[2] - label_bbox[0]
        draw.text((x + (stat_box_width - label_width) / 2, y + 115), label, fill='#aaaaaa', font=label_font)
    
    y_position += 2 * (stat_box_height + padding) + 50
    
    # Top Thread section
    section_title = "🔥 Most Viewed Thread"
    draw.text((60, y_position), section_title, fill='#667eea', font=header_font)
    y_position += 70
    
    top_thread = filtered_df.nlargest(1, 'views').iloc[0]
    thread_title = top_thread['title'][:50] + "..." if len(top_thread['title']) > 50 else top_thread['title']
    
    # Word wrap the title
    words = thread_title.split()
    lines = []
    current_line = []
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=body_font)
        if bbox[2] - bbox[0] < 900:
            current_line.append(word)
        else:
            lines.append(' '.join(current_line))
            current_line = [word]
    if current_line:
        lines.append(' '.join(current_line))
    
    for line in lines[:3]:  # Max 3 lines
        draw.text((60, y_position), line, fill='#ffffff', font=body_font)
        y_position += 40
    
    draw.text((60, y_position), f"by {top_thread['author']}", fill='#aaaaaa', font=label_font)
    y_position += 45
    draw.text((60, y_position), f"{int(top_thread['views']):,} views  •  {int(top_thread['replies']):,} replies", fill='#aaaaaa', font=label_font)
    y_position += 80
    
    # Top Authors section
    section_title = "👑 Top Contributors"
    draw.text((60, y_position), section_title, fill='#667eea', font=header_font)
    y_position += 70
    
    # Top 3 authors by threads
    author_threads = filtered_df.groupby('author').size().reset_index(name='count')
    top_authors = author_threads.nlargest(3, 'count')
    
    for idx, row in top_authors.iterrows():
        medal = ["🥇", "🥈", "🥉"][list(top_authors.index).index(idx)]
        text = f"{medal} {row['author']}: {row['count']} threads"
        draw.text((60, y_position), text, fill='#ffffff', font=body_font)
        y_position += 45
    
    y_position += 40
    
    # Footer
    footer_text = "Thank you for making The Vestibule vibrant! 🎮"
    footer_bbox = draw.textbbox((0, 0), footer_text, font=label_font)
    footer_width = footer_bbox[2] - footer_bbox[0]
    draw.text(((width - footer_width) / 2, height - 100), footer_text, fill='#667eea', font=label_font)
    
    return img

def create_wrapped_report(filtered_df, raw_df, start_date, end_date):
    """Create 2025 Wrapped-style visualizations"""
    
    if filtered_df.empty:
        st.warning("No threads found for the selected date range")
        return
    
    # Header
    st.markdown('<div class="wrapped-title">🎮 2025 WRAPPED</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="wrapped-subtitle">IGN Forum: The Vestibule<br>{start_date.strftime("%B %d")} - {end_date.strftime("%B %d, %Y")}</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Hero Stats
    st.markdown('<div class="section-header">📊 By The Numbers</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="emoji-large">🧵</div>
            <div class="stat-number">{len(filtered_df):,}</div>
            <div class="stat-label">Threads Created</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="stat-card">
            <div class="emoji-large">💬</div>
            <div class="stat-number">{int(filtered_df['replies'].sum()):,}</div>
            <div class="stat-label">Total Replies</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="stat-card">
            <div class="emoji-large">👀</div>
            <div class="stat-number">{int(filtered_df['views'].sum()):,}</div>
            <div class="stat-label">Total Views</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="stat-card">
            <div class="emoji-large">👥</div>
            <div class="stat-number">{filtered_df['author'].nunique():,}</div>
            <div class="stat-label">Active Authors</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # Top 10 Most Viewed Threads
    st.markdown('<div class="section-header">🔥 Most Viewed Threads</div>', unsafe_allow_html=True)
    top_views = filtered_df.nlargest(10, 'views')[['title', 'author', 'views', 'replies']].reset_index(drop=True)
    top_views.index = top_views.index + 1
    
    fig_top_views = go.Figure(data=[go.Table(
        header=dict(values=['<b>Rank</b>', '<b>Thread</b>', '<b>Author</b>', '<b>Views</b>', '<b>Replies</b>'],
                    fill_color='#667eea',
                    font=dict(color='white', size=14),
                    align='left'),
        cells=dict(values=[top_views.index, top_views['title'], top_views['author'], 
                          top_views['views'].apply(lambda x: f"{int(x):,}"),
                          top_views['replies'].apply(lambda x: f"{int(x):,}")],
                  fill_color='lavender',
                  font=dict(size=12),
                  align='left',
                  height=30))
    ])
    fig_top_views.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig_top_views, use_container_width=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Top 10 Most Replied Threads
    st.markdown('<div class="section-header">💬 Most Discussed Threads</div>', unsafe_allow_html=True)
    top_replies = filtered_df.nlargest(10, 'replies')[['title', 'author', 'replies', 'views']].reset_index(drop=True)
    top_replies.index = top_replies.index + 1
    
    fig_top_replies = go.Figure(data=[go.Table(
        header=dict(values=['<b>Rank</b>', '<b>Thread</b>', '<b>Author</b>', '<b>Replies</b>', '<b>Views</b>'],
                    fill_color='#764ba2',
                    font=dict(color='white', size=14),
                    align='left'),
        cells=dict(values=[top_replies.index, top_replies['title'], top_replies['author'],
                          top_replies['replies'].apply(lambda x: f"{int(x):,}"),
                          top_replies['views'].apply(lambda x: f"{int(x):,}")],
                  fill_color='#f0e6ff',
                  font=dict(size=12),
                  align='left',
                  height=30))
    ])
    fig_top_replies.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig_top_replies, use_container_width=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Top Authors Section
    st.markdown('<div class="section-header">👑 Top Contributors</div>', unsafe_allow_html=True)
    
    # Top 10 Authors by Thread Count
    st.markdown("### 🏆 Most Prolific Thread Creators")
    author_threads = filtered_df.groupby('author').size().reset_index(name='thread_count')
    author_threads = author_threads.sort_values('thread_count', ascending=False).head(10)
    
    fig_thread_count = px.bar(
        author_threads,
        x='thread_count',
        y='author',
        orientation='h',
        title="",
        labels={'thread_count': 'Threads Created', 'author': ''},
        color='thread_count',
        color_continuous_scale='Purples'
    )
    fig_thread_count.update_layout(
        showlegend=False,
        height=400,
        yaxis={'categoryorder': 'total ascending'},
        margin=dict(l=0, r=0, t=20, b=0)
    )
    st.plotly_chart(fig_thread_count, use_container_width=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Top 10 Authors by Total Views
    st.markdown("### 👀 Most Viewed Thread Creators")
    author_views = filtered_df.groupby('author')['views'].sum().reset_index()
    author_views = author_views.sort_values('views', ascending=False).head(10)
    
    fig_author_views = px.bar(
        author_views,
        x='views',
        y='author',
        orientation='h',
        title="",
        labels={'views': 'Total Views', 'author': ''},
        color='views',
        color_continuous_scale='Blues'
    )
    fig_author_views.update_layout(
        showlegend=False,
        height=400,
        yaxis={'categoryorder': 'total ascending'},
        margin=dict(l=0, r=0, t=20, b=0)
    )
    st.plotly_chart(fig_author_views, use_container_width=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Top 10 Authors by Total Replies
    st.markdown("### 💬 Most Discussion-Generating Authors")
    author_replies = filtered_df.groupby('author')['replies'].sum().reset_index()
    author_replies = author_replies.sort_values('replies', ascending=False).head(10)
    
    fig_author_replies = px.bar(
        author_replies,
        x='replies',
        y='author',
        orientation='h',
        title="",
        labels={'replies': 'Total Replies', 'author': ''},
        color='replies',
        color_continuous_scale='Reds'
    )
    fig_author_replies.update_layout(
        showlegend=False,
        height=400,
        yaxis={'categoryorder': 'total ascending'},
        margin=dict(l=0, r=0, t=20, b=0)
    )
    st.plotly_chart(fig_author_replies, use_container_width=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Activity Timeline
    st.markdown('<div class="section-header">📅 Activity Timeline</div>', unsafe_allow_html=True)
    
    daily_activity = filtered_df.groupby(filtered_df['timestamp'].dt.date).size().reset_index()
    daily_activity.columns = ['date', 'threads']
    
    fig_timeline = px.area(
        daily_activity,
        x='date',
        y='threads',
        title="",
        labels={'date': 'Date', 'threads': 'Threads Created'},
        color_discrete_sequence=['#667eea']
    )
    fig_timeline.update_layout(
        height=350,
        margin=dict(l=0, r=0, t=20, b=0),
        hovermode='x unified'
    )
    st.plotly_chart(fig_timeline, use_container_width=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Hour of Day Activity
    st.markdown('<div class="section-header">🕐 Peak Activity Hours</div>', unsafe_allow_html=True)
    
    filtered_df['hour'] = filtered_df['timestamp'].dt.hour
    hourly_counts = filtered_df.groupby('hour').size().reset_index()
    hourly_counts.columns = ['hour', 'thread_count']
    
    all_hours = pd.DataFrame({'hour': range(24)})
    hourly_counts = all_hours.merge(hourly_counts, on='hour', how='left').fillna(0)
    
    fig_hourly = px.bar(
        hourly_counts,
        x='hour',
        y='thread_count',
        title="",
        labels={'hour': 'Hour of Day (UTC)', 'thread_count': 'Threads Created'},
        color='thread_count',
        color_continuous_scale='Viridis'
    )
    fig_hourly.update_xaxes(tickmode='linear', tick0=0, dtick=1)
    fig_hourly.update_layout(
        showlegend=False,
        height=350,
        margin=dict(l=0, r=0, t=20, b=0)
    )
    st.plotly_chart(fig_hourly, use_container_width=True)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # Footer
    st.markdown("---")
    st.markdown('<div style="text-align: center; color: #666; font-size: 0.9rem;">Thank you for making The Vestibule vibrant in 2025! 🎮</div>', unsafe_allow_html=True)

def main():
    # Sidebar controls
    st.sidebar.title("⚙️ Settings")
    
    num_pages = st.sidebar.number_input(
        "Pages to scrape", 
        min_value=1, 
        max_value=2000, 
        value=10,
        help="More pages = more complete data"
    )
    
    end_date_default = datetime.now().date() - timedelta(days=1)
    start_date_default = end_date_default - timedelta(days=29)
    
    date_range = st.sidebar.date_input(
        "Date range:",
        value=(start_date_default, end_date_default),
        help="Select date range for the Wrapped report"
    )
    
    if len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = date_range[0] if date_range else start_date_default
        end_date = start_date
    
    if st.sidebar.button("🚀 Generate Wrapped Report", type="primary"):
        st.info(f"Scraping {num_pages} pages...")
        
        with st.spinner("Collecting forum data..."):
            raw_df = scrape_forum_data(num_pages)
        
        if not raw_df.empty:
            st.success(f"Scraped {len(raw_df)} threads!")
            
            filtered_df = filter_by_date(raw_df, start_date, end_date)
            
            if not filtered_df.empty:
                st.session_state.filtered_df = filtered_df
                st.session_state.raw_df = raw_df
                st.session_state.start_date = start_date
                st.session_state.end_date = end_date
            else:
                st.warning(f"No threads found in selected range. Using all data.")
                st.session_state.filtered_df = raw_df
                st.session_state.raw_df = raw_df
                st.session_state.start_date = start_date
                st.session_state.end_date = end_date
        else:
            st.error("Failed to scrape data. Please try again.")
    
    # Display wrapped report
    if 'filtered_df' in st.session_state:
        create_wrapped_report(
            st.session_state.filtered_df, 
            st.session_state.raw_df,
            st.session_state.start_date,
            st.session_state.end_date
        )
        
        # Download option
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 💾 Export Data")
        
        col1, col2 = st.sidebar.columns(2)
        
        with col1:
            csv = st.session_state.filtered_df.to_csv(index=False)
            st.download_button(
                label="📥 CSV",
                data=csv,
                file_name=f"ign_wrapped_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            # Generate infographic
            if st.button("🎨 Image", use_container_width=True):
                with st.spinner("Creating infographic..."):
                    img = create_infographic(
                        st.session_state.filtered_df,
                        st.session_state.start_date,
                        st.session_state.end_date
                    )
                    
                    # Convert to bytes
                    buf = io.BytesIO()
                    img.save(buf, format='PNG')
                    byte_im = buf.getvalue()
                    
                    st.download_button(
                        label="📥 Download Infographic",
                        data=byte_im,
                        file_name=f"ign_wrapped_{datetime.now().strftime('%Y%m%d')}.png",
                        mime="image/png"
                    )
    else:
        st.info("👈 Configure settings and click 'Generate Wrapped Report' to begin!")

if __name__ == "__main__":
    main()
