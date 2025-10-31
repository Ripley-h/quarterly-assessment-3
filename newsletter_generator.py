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
# Set up logging to suppress unnecessary warnings
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
        Creates the full newsletter content with an introduction, summaries, and a closing.
        """
        if not articles:
            return "No articles found for the newsletter."

        total_tasks = 2 + len(articles)
        newsletter_output = [f"# {title}\n\nHere's your daily update on {topic}:\n"]

        with Progress() as progress:
            task = progress.add_task("[cyan]Generating newsletter...", total=total_tasks)

            for i, article in enumerate(articles):
                progress.update(task, advance=1, description=f"[cyan]Summarizing article {i+1}/{len(articles)}...")
                summary = self.summarize_article(article.get('content') or article.get('description', ''))
                newsletter_output.append(f"## {article['title']}\n\n{summary}\n\n[Read more]({article['url']})\n")

            progress.update(task, advance=1, description="[cyan]Finalizing newsletter...")
            newsletter_output.append("\nWe hope you enjoyed this update. Stay tuned for more!\n")
            progress.update(task, advance=1, description="[green]Done!")

        return "\n".join(newsletter_output)

    def send_email(self, subject, body, sender_email, recipient_email, smtp_server, smtp_port, smtp_user, smtp_password):
        """
        Sends the newsletter via email using SMTP.
        """
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

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
    parser.add_argument("-o", "--output-file", type=str, help="Output filename to save the newsletter")

    args = parser.parse_args()

    # --- Create cache directory ---
    if not os.path.exists("./cache"):
        os.makedirs("./cache")

    generator = NewsletterGenerator(args.news_api_key, args.openai_api_key)
    articles = generator.fetch_articles(args.topic, args.max)

    if articles:
        newsletter_text = generator.create_newsletter_content(args.title, args.topic, articles)
        
        if args.output_file:
            with open(args.output_file, "w") as f:
                f.write(newsletter_text)
            print(f"Newsletter saved to {args.output_file}")
        else:
            print(newsletter_text)

        if args.send_email:
            if all([args.recipient_email, args.sender_email, args.smtp_server, args.smtp_user, args.smtp_password]):
                generator.send_email(
                    subject=args.title,
                    body=newsletter_text,
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