#!/usr/bin/env python3
"""
Wikipedia Feed - Desktop GUI Application
A simple desktop app for browsing Wikipedia articles from ZIM files or live API.
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import json
import os
import sys
import random
import requests

# Wikipedia API headers
WIKI_HEADERS = {
    'User-Agent': 'WikipediaFeed/1.0 (Desktop App)'
}

# Jeopardy weights
JEOPARDY_WEIGHTS = {
    'History': 20, 'Science': 18, 'Geography': 15, 'Literature': 12,
    'Arts': 10, 'Sports': 8, 'Politics': 7, 'Religion': 5,
    'Nature': 3, 'Technology': 2
}

CATEGORIES = ['Science', 'History', 'Geography', 'Literature', 'Arts', 
              'Sports', 'Politics', 'Religion', 'Nature', 'Technology', 'People']


class WikipediaFeedApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Wikipedia Feed")
        self.root.geometry("900x700")
        self.root.configure(bg="#0d1117")
        
        # State
        self.zim_path = None
        self.zim_archive = None
        self.articles = []
        self.current_index = 0
        self.algorithm = "random"
        self.selected_category = None
        self.user_clicks = []
        
        self.setup_ui()
        
        # Try to load last ZIM path
        self.load_last_path()
    
    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#161b22", pady=10)
        header.pack(fill=tk.X)
        
        tk.Label(header, text="📚 Wikipedia Feed", font=("Georgia", 18, "bold"),
                fg="#e6edf3", bg="#161b22").pack(side=tk.LEFT, padx=20)
        
        # Source selection
        self.source_var = tk.StringVar(value="live")
        source_frame = tk.Frame(header, bg="#161b22")
        source_frame.pack(side=tk.RIGHT, padx=20)
        
        tk.Radiobutton(source_frame, text="💾 Local", variable=self.source_var, 
                      value="local", bg="#161b22", fg="#8b949e", 
                      selectcolor="#21262d", command=self.on_source_change).pack(side=tk.LEFT)
        tk.Radiobutton(source_frame, text="🌐 Live", variable=self.source_var,
                      value="live", bg="#161b22", fg="#8b949e",
                      selectcolor="#21262d", command=self.on_source_change).pack(side=tk.LEFT, padx=10)
        
        # Controls
        controls = tk.Frame(self.root, bg="#0d1117", pady=10)
        controls.pack(fill=tk.X, padx=20)
        
        # Algorithm dropdown
        tk.Label(controls, text="Algorithm:", bg="#0d1117", fg="#8b949e").pack(side=tk.LEFT)
        self.algorithm_combo = ttk.Combobox(controls, values=["Random", "User-Based", "Jeopardy", "Category"],
                                           state="readonly", width=15)
        self.algorithm_combo.set("Random")
        self.algorithm_combo.pack(side=tk.LEFT, padx=10)
        self.algorithm_combo.bind("<<ComboboxSelected>>", self.on_algorithm_change)
        
        # Category dropdown
        tk.Label(controls, text="Category:", bg="#0d1117", fg="#8b949e").pack(side=tk.LEFT, padx=20)
        self.category_combo = ttk.Combobox(controls, values=[""] + CATEGORIES, state="readonly", width=15)
        self.category_combo.pack(side=tk.LEFT, padx=10)
        self.category_combo.bind("<<ComboboxSelected>>", self.on_category_change)
        
        # Load button
        tk.Button(controls, text="🔄 Load Articles", command=self.load_articles,
                 bg="#58a6ff", fg="#0d1117", font=("Arial", 10, "bold"),
                 padx=15, pady=5).pack(side=tk.RIGHT)
        
        # Content area with scrollbar
        content_frame = tk.Frame(self.root, bg="#0d1117")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.canvas = tk.Canvas(content_frame, bg="#0d1117", highlightthickness=0)
        scrollbar = ttk.Scrollbar(content_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="#0d1117")
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Status bar
        self.status_label = tk.Label(self.root, text="Select source and click Load",
                                   bg="#161b22", fg="#8b949e", pady=8)
        self.status_label.pack(fill=tk.X)
        
        # Progress bar
        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
    
    def on_source_change(self):
        source = self.source_var.get()
        if source == "local":
            self.select_zim_file()
        else:
            self.status_label.config(text="Live mode - click Load to fetch articles")
    
    def select_zim_file(self):
        filename = filedialog.askopenfilename(
            title="Select ZIM File",
            filetypes=[("ZIM files", "*.zim"), ("All files", "*.*")]
        )
        if filename:
            self.zim_path = filename
            self.save_last_path(filename)
            self.status_label.config(text=f"Loaded: {os.path.basename(filename)}")
            self.init_zim()
        else:
            self.source_var.set("live")
    
    def init_zim(self):
        if not self.zim_path or not os.path.exists(self.zim_path):
            return
        
        try:
            import libzim
            self.zim_archive = libzim.Archive(self.zim_path)
            self.status_label.config(text=f"ZIM loaded: {self.zim_archive.article_count} articles")
        except ImportError:
            messagebox.showwarning("Warning", "libzim not installed. Install with: pip install libzim\nUsing Live mode instead.")
            self.source_var.set("live")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load ZIM: {e}")
            self.source_var.set("live")
    
    def load_articles(self):
        self.status_label.config(text="Loading articles...")
        self.progress.pack(fill=tk.X)
        self.progress.start()
        
        thread = threading.Thread(target=self._load_articles)
        thread.daemon = True
        thread.start()
    
    def _load_articles(self):
        source = self.source_var.get()
        algorithm = self.algorithm_combo.get()
        category = self.category_combo.get() if self.category_combo.get() else None
        
        articles = []
        
        if source == "local" and self.zim_archive:
            articles = self.get_local_articles(algorithm, category)
        else:
            articles = self.get_live_articles(algorithm, category)
        
        self.articles = articles
        self.current_index = 0
        
        self.root.after(0, self.display_articles)
    
    def get_local_articles(self, algorithm, category, count=20):
        articles = []
        
        for _ in range(count * 3):
            try:
                entry = self.zim_archive.get_random_entry()
                if not entry or not entry.path.startswith('A/'):
                    continue
                
                item = entry.get_item()
                if item.size > 50000:
                    continue
                
                content = item.content.tobytes().decode('utf-8', errors='ignore')
                
                articles.append({
                    'title': entry.title,
                    'content': content[:500],
                    'path': entry.path
                })
                
                if len(articles) >= count:
                    break
            except:
                continue
        
        return articles
    
    def get_live_articles(self, algorithm, category, count=20):
        articles = []
        
        for _ in range(count * 2):
            try:
                resp = requests.get(
                    'https://en.wikipedia.org/api/rest_v1/page/random/summary',
                    headers=WIKI_HEADERS, timeout=10
                )
                if resp.status_code != 200:
                    continue
                
                data = resp.json()
                title = data.get('title', '')
                
                if title.startswith('Wikipedia:') or title.startswith('Template:'):
                    continue
                
                articles.append({
                    'title': title,
                    'content': data.get('extract', '')[:500],
                    'path': title.replace(' ', '_'),
                    'thumbnail': data.get('thumbnail', {}).get('source')
                })
                
                if len(articles) >= count:
                    break
            except:
                continue
        
        return articles
    
    def display_articles(self):
        self.progress.stop()
        self.progress.pack_forget()
        
        # Clear existing
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        if not self.articles:
            self.status_label.config(text="No articles loaded")
            return
        
        # Display cards
        for i, article in enumerate(self.articles):
            self.create_article_card(article, i)
        
        self.status_label.config(text=f"Showing {len(self.articles)} articles")
    
    def create_article_card(self, article, index):
        card = tk.Frame(self.scrollable_frame, bg="#21262d", bd=1, relief=tk.FLAT)
        card.pack(fill=tk.X, pady=8, padx=5)
        
        # Title
        title_label = tk.Label(card, text=article['title'], font=("Georgia", 12, "bold"),
                              fg="#e6edf3", bg="#21262d", wraplength=700, justify=tk.LEFT)
        title_label.pack(anchor=tk.W, padx=12, pady=(12, 5))
        
        # Preview
        preview = article.get('content', '')[:200] + '...'
        preview_label = tk.Label(card, text=preview, font=("Arial", 9),
                               fg="#8b949e", bg="#21262d", wraplength=700, justify=tk.LEFT)
        preview_label.pack(anchor=tk.W, padx=12, pady=(0, 8))
        
        # Word count
        word_count = len(article.get('content', '').split())
        tk.Label(card, text=f"{word_count} words", font=("Arial", 8),
                fg="#58a6ff", bg="#21262d").pack(anchor=tk.W, padx=12, pady=(0, 12))
    
    def on_algorithm_change(self, event=None):
        algo = self.algorithm_combo.get()
        
        if algo == "Category":
            self.category_combo.config(state="readonly")
        else:
            self.category_combo.set("")
            self.category_combo.config(state="disabled")
    
    def on_category_change(self, event=None):
        self.selected_category = self.category_combo.get()
    
    def load_last_path(self):
        config_path = os.path.expanduser("~/.wikipedia-feed.conf")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    if config.get('zim_path') and os.path.exists(config['zim_path']):
                        self.zim_path = config['zim_path']
                        self.source_var.set("local")
                        self.root.after(100, self.init_zim)
            except:
                pass
    
    def save_last_path(self, path):
        config_path = os.path.expanduser("~/.wikipedia-feed.conf")
        try:
            with open(config_path, 'w') as f:
                json.dump({'zim_path': path}, f)
        except:
            pass


def main():
    root = tk.Tk()
    app = WikipediaFeedApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
