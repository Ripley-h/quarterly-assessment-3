#!/usr/bin/env python3

"""
llm-newsletter-generator is a Python script designed to generate and email newsletters
from news articles fetched via a news API. It uses AI to summarize articles and
create compelling newsletter content.

Copyright (c) 2024-PRESENT Sam Estrin
This script is licensed under the MIT License (see LICENSE for details)
GitHub: https://github.com/samestrin/newsletter-generator
"""

import logging
import argparse
import requests
import hashlib
import sys
import os
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import openai
import json
from rich.progress import Progress

# --- Basic Configuration ---
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# --- Custom Help Formatter (No changes) ---
class CustomHelpFormatter(argparse.HelpFormatter):
    """Custom help formatter for argparse."""
    def _format_action_invocation(self, action):
        if not action.option_strings:
            metavar, = self._metavar_formatter(action, action.dest)(1)
            return metavar
        else:
            parts = [', '.join(action.option_strings)]
            if action.nargs != 0:
                parts.append(self._format_args(action, action.dest))
            return ' '.join(parts)

    def _split_lines(self, text, width):
        return text.splitlines()

# --- Newsletter Generator Class (Modified) ---
class NewsletterGenerator:
    """
    Generates and emails newsletters from news articles using AI.
    """
    def __init__(self, news_api_key, openai_api_key, cache_timeout=3600):
        self.news_api_key = news_api_key
        self.cache_timeout = cache_timeout
        openai.api_key = openai_api_key

    def fetch_articles(self, topic, max_articles=5):
        """
        Fetches articles from the News API.
        """
        url = f"https://newsapi.org/v2/everything?q={topic}&apiKey={self.news_api_key}&pageSize={max_articles}&language=en"
        cache_file = f"./cache/{hashlib.md5(url.encode()).hexdigest()}.json"

        if os.path.exists(cache_file) and (time.time() - os.path.getmtime(cache_file) < self.cache_timeout):
            print("Using cached articles.")
            with open(cache_file, "r") as f:
                return json.load(f)

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            with open(cache_file, "w") as f:
                json.dump(data['articles'], f)
            return data['articles']
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching articles: {e}")
            return None

    def summarize_article(self, article_content):
        """
        Summarizes an article using the OpenAI API.
        """
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes news articles for a newsletter."},
                    {"role": "user", "content": f"Please summarize the following article in a concise, email-friendly format:\n\n{article_content}"}
                ],
                max_tokens=150
            )
            return response.choices[0].message['content'].strip()
        except Exception as e:
            logger.error(f"Error summarizing article: {e}")
            return "Summary could not be generated."

    def create_newsletter_content(self, title, topic, articles):
        """
        Creates the full newsletter content as an HTML string with styling.
        """
        if not articles:
            return "No articles found for the newsletter."

        # Start of the HTML document with embedded CSS for styling
        html_content = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                h1 {{
                    color: #2c3e50;
                    text-align: center;
                }}
                h2 {{
                    color: #3498db;
                    border-bottom: 2px solid #ecf0f1;
                    padding-bottom: 10px;
                }}
                .article {{
                    margin-bottom: 25px;
                }}
                .summary-header {{
                    font-weight: bold;
                    color: #7f8c8d;
                    margin-bottom: 5px;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    font-size: 0.9em;
                    color: #95a5a6;
                }}
                a {{
                    color: #3498db;
                    text-decoration: none;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{title}</h1>
                <p>Here is your daily update on <strong>{topic}</strong>:</p>
        """

        with Progress() as progress:
            task = progress.add_task("[cyan]Generating newsletter...", total=len(articles))

            for article in articles:
                progress.update(task, advance=1, description=f"[cyan]Summarizing article...")
                
                # Use description as fallback if content is null
                content_to_summarize = article.get('content') or article.get('description', '')
                summary = self.summarize_article(content_to_summarize)

                html_content += f"""
                <div class="article">
                    <h2>{article['title']}</h2>
                    <p class="summary-header">Summary</p>
                    <p>{summary}</p>
                    <a href="{article['url']}" target="_blank">Read Full Article</a>
                </div>
                """

        html_content += """
                <div class="footer">
                    <p>This newsletter was generated automatically. We hope you enjoyed this update!</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html_content

    def send_email(self, subject, body, sender_email, recipient_email, smtp_server, smtp_port, smtp_user, smtp_password):
        """
        Sends the newsletter via email using SMTP.
        """
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Attach the body as HTML
        msg.attach(MIMEText(body, 'html'))

        try:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
            print(f"Newsletter sent successfully to {recipient_email}")
        except smtplib.SMTPException as e:
            logger.error(f"Failed to send email: {e}")

# --- Main Function (Modified) ---
def main():
    """
    Main function to handle command-line arguments and generate the newsletter.
    """
    start_time = time.time()

    parser = argparse.ArgumentParser(description="Generate and email a newsletter from news articles.", formatter_class=CustomHelpFormatter)
    # --- News & Content Arguments ---
    parser.add_argument("-t", "--title", type=str, required=True, help="Title of the newsletter")
    parser.add_argument("-to", "--topic", type=str, required=True, help="Topic for the news articles")
    parser.add_argument("--max", type=int, default=5, help="Maximum number of articles to include")

    # --- API Key Arguments ---
    parser.add_argument("--news-api-key", type=str, required=True, help="API key for News API")
    parser.add_argument("--openai-api-key", type=str, required=True, help="API key for OpenAI")

    # --- Email Arguments ---
    parser.add_argument("--send-email", action='store_true', help="Flag to send the newsletter via email")
    parser.add_argument("--recipient-email", type=str, help="Recipient's email address")
    parser.add_argument("--sender-email", type=str, help="Sender's email address")
    parser.add_argument("--smtp-server", type=str, help="SMTP server address")
    parser.add_argument("--smtp-port", type=int, default=587, help="SMTP server port")
    parser.add_argument("--smtp-user", type=str, help="SMTP username")
    parser.add_argument("--smtp-password", type=str, help="SMTP password")
    
    # --- Output Arguments ---
    parser.add_argument("-o", "--output-file", type=str, help="Output filename to save the newsletter (e.g., newsletter.html)")

    args = parser.parse_args()

    # --- Create cache directory if it doesn't exist ---
    if not os.path.exists("./cache"):
        os.makedirs("./cache")

    generator = NewsletterGenerator(args.news_api_key, args.openai_api_key)
    articles = generator.fetch_articles(args.topic, args.max)

    if articles:
        newsletter_html = generator.create_newsletter_content(args.title, args.topic, articles)
        
        if args.output_file:
            with open(args.output_file, "w", encoding="utf-8") as f:
                f.write(newsletter_html)
            print(f"Newsletter saved to {args.output_file}")
        else:
            # Print a message as the HTML output is too long for the console
            print("Newsletter content generated successfully. Use -o to save to a file or --send-email to send.")

        if args.send_email:
            if all([args.recipient_email, args.sender_email, args.smtp_server, args.smtp_user, args.smtp_password]):
                generator.send_email(
                    subject=args.title,
                    body=newsletter_html,
                    sender_email=args.sender_email,
                    recipient_email=args.recipient_email,
                    smtp_server=args.smtp_server,
                    smtp_port=args.smtp_port,
                    smtp_user=args.smtp_user,
                    smtp_password=args.smtp_password
                )
            else:
                print("To send an email, you must provide all required email arguments.")
    else:
        print("Failed to generate newsletter because no articles could be fetched.")

    print(f"\nTotal runtime: {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    main()