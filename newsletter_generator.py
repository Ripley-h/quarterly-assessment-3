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

# --- Custom Help Formatter ---
class CustomHelpFormatter(argparse.HelpFormatter):
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

# --- Newsletter Generator Class ---
class NewsletterGenerator:
    def __init__(self, news_api_key, openai_api_key, cache_timeout=3600):
        self.news_api_key = news_api_key
        self.cache_timeout = cache_timeout
        openai.api_key = openai_api_key

    def fetch_articles(self, topic, max_articles=5):
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
        try:
            prompt_message = f"Please summarize the following article in a concise, email-friendly format, ensuring the summary is between 3 and 5 sentences long:\n\n{article_content}"
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes news articles for a newsletter."},
                    {"role": "user", "content": prompt_message}
                ],
                max_tokens=200
            )
            return response.choices[0].message['content'].strip()
        except Exception as e:
            logger.error(f"Error summarizing article: {e}")
            return "Summary could not be generated."

    def create_newsletter_content(self, title, topic, articles):
        if not articles:
            return "No articles found for the newsletter."

        html_content = f"""
        <html>
        <head>
            <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap" rel="stylesheet">
            <style>
                body {{
                    font-family: 'Montserrat', sans-serif;
                    line-height: 1.6;
                    color: #34495e;
                    background-color: #f4f7f6;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 20px auto;
                    padding: 25px;
                    background-color: #ffffff;
                    border-radius: 8px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.05);
                }}
                h1 {{ color: #2c3e50; text-align: center; font-weight: 700; }}
                h2 {{ color: #1abc9c; border-bottom: 2px solid #f4f7f6; padding-bottom: 10px; font-weight: 700; }}
                .article {{ margin-bottom: 25px; }}
                .footer {{ text-align: center; margin-top: 30px; font-size: 0.9em; color: #95a5a6; }}
                a {{ color: #1abc9c; text-decoration: none; font-weight: bold; }}
                a:hover {{ text-decoration: underline; }}
                hr {{ border: 0; height: 1px; background: #e0e5e4; margin: 30px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{title}</h1>
                <p>Here is your daily update on <strong>{topic}</strong>:</p>
        """

        with Progress() as progress:
            task = progress.add_task("[cyan]Generating newsletter...", total=len(articles))
            for index, article in enumerate(articles):
                progress.update(task, advance=1, description=f"[cyan]Summarizing article...")
                content_to_summarize = article.get('content') or article.get('description', '')
                summary = self.summarize_article(content_to_summarize)
                html_content += f"""
                <div class="article">
                    <h2>{article['title']}</h2>
                    <p>{summary}</p>
                    <a href="{article['url']}" target="_blank">Read Full Article &rarr;</a>
                </div>
                """
                if index < len(articles) - 1:
                    html_content += "<hr>"

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
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        try:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
            print(f"Newsletter sent successfully to {recipient_email}")
        except smtplib.SMTPException as e:
            logger.error(f"Failed to send email: {e}")

# --- Main Function ---
def main():
    start_time = time.time()
    parser = argparse.ArgumentParser(description="Generate and email a newsletter from news articles.", formatter_class=CustomHelpFormatter)
    parser.add_argument("-t", "--title", type=str, required=True, help="Title of the newsletter")
    parser.add_argument("-to", "--topic", type=str, required=True, help="Topic for the news articles")
    parser.add_argument("--max", type=int, default=5, help="Maximum number of articles to include")
    parser.add_argument("--news-api-key", type=str, required=True, help="API key for News API")
    parser.add_argument("--openai-api-key", type=str, required=True, help="API key for OpenAI")
    parser.add_argument("--send-email", action='store_true', help="Flag to send the newsletter via email")
    parser.add_argument("--recipient-email", type=str, help="Recipient's email address")
    parser.add_argument("--sender-email", type=str, help="Sender's email address")
    parser.add_argument("--smtp-server", type=str, help="SMTP server address")
    parser.add_argument("--smtp-port", type=int, default=587, help="SMTP server port")
    parser.add_argument("--smtp-user", type=str, help="SMTP username")
    parser.add_argument("--smtp-password", type=str, help="SMTP password")
    parser.add_argument("-o", "--output-file", type=str, help="Output filename to save the newsletter (e.g., newsletter.html)")

    args = parser.parse_args()

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