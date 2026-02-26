import feedparser
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from newspaper import Article

RSS_FEEDS=[
"https://feeds.reuters.com/reuters/worldNews",
"http://feeds.bbci.co.uk/news/world/rss.xml",
"https://www.economist.com/international/rss.xml"
]

EMAIL_ADDRESS=os.getenv("EMAIL_USER")
EMAIL_PASSWORD=os.getenv("EMAIL_PASS")

def get_long_summary(url):
    try:
        article=Article(url)
        article.download()
        article.parse()
        article.nlp()
        text=article.text
        summary=article.summary
        if len(summary)<500:
            summary=summary+"\n\n"+text[:1000]
        return summary[:1500]
    except:
        return "Full text not available."

def fetch_news():
    all_entries=[]
    for feed in RSS_FEEDS:
        parsed=feedparser.parse(feed)
        all_entries.extend(parsed.entries[:5])
    return all_entries[:5]

def build_email():
    news_list=fetch_news()
    body="🌍 Daily Global News Briefing\n\n"
    for i,item in enumerate(news_list,1):
        title=item.title
        link=item.link
        summary=get_long_summary(link)
        body+=f"{i}. {title}\n\n{summary}\n\nRead more: {link}\n\n"
    return body

def send_email(content):
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        raise ValueError("Missing email credentials")

    msg=MIMEMultipart()
    msg["From"]=EMAIL_ADDRESS
    msg["To"]=EMAIL_ADDRESS
    msg["Subject"]="Daily Global News"

    msg.attach(MIMEText(content,"plain"))

    with smtplib.SMTP("smtp.gmail.com",587) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS,EMAIL_PASSWORD)
        server.send_message(msg)

def main():
    print("📡 Daily News Bot starting…")
    email_body=build_email()
    send_email(email_body)
    print("✅ Email sent successfully!")

if __name__=="__main__":
    main()
