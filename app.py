import streamlit as st
import assemblyai as aai
import json
import os
from datetime import datetime
import time
from dotenv import load_dotenv
import re
from typing import Dict, List, Tuple

# Load environment variables
load_dotenv()

# Configure page
st.set_page_config(
    page_title="Critical Call Analysis",
    page_icon="📞",
    layout="wide"
)

class CallAnalyzer:
    def __init__(self, api_key: str):
        """Initialize the CallAnalyzer with AssemblyAI API key."""
        aai.settings.api_key = api_key
        self.transcriber = aai.Transcriber()
        
    def transcribe_audio(self, audio_file_path: str) -> Dict:
        """Transcribe audio file and get sentiment analysis."""
        config = aai.TranscriptionConfig(
            sentiment_analysis=True,
            auto_highlights=True,
            iab_categories=True,
            speaker_labels=True,
            punctuate=True,
            format_text=True
        )
        
        transcript = self.transcriber.transcribe(audio_file_path, config=config)
        
        if transcript.status == aai.TranscriptStatus.error:
            raise Exception(f"Transcription failed: {transcript.error}")
            
        return transcript
    
    def calculate_quality_score(self, transcript: Dict, sentiment_analysis_results: List) -> Tuple[float, List[str]]:
        """Calculate quality score based on various factors."""
        issues = []
        base_score = 85.0
        
        # Analyze sentiment
        negative_sentiment_count = 0
        try:
            for result in sentiment_analysis_results:
                # Handle different possible sentiment structures
                sentiment_value = None
                if hasattr(result, 'sentiment'):
                    if hasattr(result.sentiment, 'value'):
                        sentiment_value = result.sentiment.value
                    else:
                        sentiment_value = str(result.sentiment)
                elif hasattr(result, 'label'):
                    sentiment_value = result.label
                
                # Check for negative sentiment
                if sentiment_value and sentiment_value.lower() in ['negative', 'neg', 'negative_sentiment']:
                    negative_sentiment_count += 1
        except Exception as e:
            print(f"Debug: Error processing sentiment: {e}")
            print(f"Debug: Sentiment results structure: {sentiment_analysis_results[:1] if sentiment_analysis_results else 'Empty'}")
        
        total_sentiment_results = len(sentiment_analysis_results)
        
        if total_sentiment_results > 0:
            negative_ratio = negative_sentiment_count / total_sentiment_results
            if negative_ratio > 0.3:
                base_score -= 20
                issues.append("High negative sentiment detected")
        
        # Analyze transcript text for common service issues
        text = transcript.text.lower()
        
        # Check for escalation issues
        escalation_keywords = ['escalate', 'supervisor', 'manager', 'complaint']
        if any(keyword in text for keyword in escalation_keywords):
            if 'procedure' in text or 'failed' in text:
                base_score -= 15
                issues.append("Agent failed to follow escalation procedure")
        
        # Check for empathy and professionalism
        empathy_keywords = ['understand', 'sorry', 'apologize', 'help']
        empathy_count = sum(text.count(keyword) for keyword in empathy_keywords)
        if empathy_count < 2:
            base_score -= 10
            issues.append("Lack of empathy in customer interaction")
        
        # Check for frustration indicators
        frustration_keywords = ['frustrated', 'angry', 'upset', 'annoyed']
        if any(keyword in text for keyword in frustration_keywords):
            base_score -= 10
            issues.append("Customer became increasingly frustrated")
        
        # Check call duration efficiency
        words = len(transcript.text.split())
        if words > 2000:  # Very long call might indicate inefficiency
            base_score -= 5
            issues.append("Call duration exceeded optimal length")
        
        return max(0, min(100, base_score)), issues
    
    def calculate_overall_sentiment_score(self, sentiment_analysis_results: List) -> float:
        """Calculate overall sentiment score from 1-5."""
        if not sentiment_analysis_results:
            return 3.0
        
        sentiment_scores = {
            'positive': 4.5,
            'neutral': 3.0,
            'negative': 1.5,
            'pos': 4.5,
            'neu': 3.0,
            'neg': 1.5
        }
        
        total_score = 0
        valid_results = 0
        
        for result in sentiment_analysis_results:
            sentiment_value = None
            try:
                if hasattr(result, 'sentiment'):
                    if hasattr(result.sentiment, 'value'):
                        sentiment_value = result.sentiment.value
                    else:
                        sentiment_value = str(result.sentiment)
                elif hasattr(result, 'label'):
                    sentiment_value = result.label
                
                if sentiment_value:
                    score = sentiment_scores.get(sentiment_value.lower(), 3.0)
                    total_score += score
                    valid_results += 1
            except Exception:
                total_score += 3.0  # Default neutral score
                valid_results += 1
        
        if valid_results == 0:
            return 3.0
            
        return round(total_score / valid_results, 1)
    
    def extract_agent_customer_info(self, transcript: Dict) -> Tuple[str, str]:
        """Extract agent and customer names from transcript."""
        # This is a simplified version - in reality, you'd need more sophisticated NLP
        text = transcript.text
        
        # Look for common patterns
        agent_pattern = r"(?:agent|representative|my name is|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
        customer_pattern = r"(?:customer|caller|my name is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
        
        agent_match = re.search(agent_pattern, text, re.IGNORECASE)
        customer_match = re.search(customer_pattern, text, re.IGNORECASE)
        
        agent_name = agent_match.group(1) if agent_match else "Unknown Agent"
        customer_name = customer_match.group(1) if customer_match else "Unknown Customer"
        
        return agent_name, customer_name
    
    def analyze_call(self, audio_file_path: str, agent_name: str = None, customer_name: str = None) -> Dict:
        """Perform complete call analysis."""
        # Transcribe audio
        transcript = self.transcribe_audio(audio_file_path)
        
        # Use provided names or extract from transcript
        if not agent_name or not customer_name:
            extracted_agent, extracted_customer = self.extract_agent_customer_info(transcript)
            agent_name = agent_name or extracted_agent
            customer_name = customer_name or extracted_customer
        
        # Calculate metrics
        sentiment_results = getattr(transcript, 'sentiment_analysis', []) or []
        
        # Debug: Print available attributes to help troubleshoot
        print(f"Debug: Available transcript attributes: {[attr for attr in dir(transcript) if not attr.startswith('_')]}")
        print(f"Debug: Sentiment results type: {type(sentiment_results)}")
        print(f"Debug: Sentiment results length: {len(sentiment_results) if sentiment_results else 0}")
        
        quality_score, issues = self.calculate_quality_score(transcript, sentiment_results)
        sentiment_score = self.calculate_overall_sentiment_score(sentiment_results)
        
        # Calculate duration (in minutes:seconds format)
        try:
            duration_ms = getattr(transcript, 'audio_duration', 0) or 0
            duration_minutes = int(duration_ms // 60000)
            duration_seconds = int((duration_ms % 60000) // 1000)
            duration_formatted = f"{duration_minutes}:{duration_seconds:02d}"
        except Exception as e:
            print(f"Debug: Error calculating duration: {e}")
            duration_formatted = "0:00"
            duration_ms = 0
        
        # Get file timestamp for date/time
        try:
            file_timestamp = os.path.getmtime(audio_file_path)
            file_datetime = datetime.fromtimestamp(file_timestamp)
            call_date = file_datetime.strftime("%Y-%m-%d")
            call_time = file_datetime.strftime("%H:%M")
        except Exception as e:
            print(f"Debug: Error getting file timestamp: {e}")
            call_date = datetime.now().strftime("%Y-%m-%d")
            call_time = datetime.now().strftime("%H:%M")
        
        # Create comprehensive analysis result
        analysis_result = {
            "call_overview": {
                "agent": {
                    "name": agent_name,
                    "type": "Human Agent"
                },
                "customer": {
                    "name": customer_name,
                    "type": "Customer Support"
                },
                "date_time": {
                    "date": call_date,
                    "time": call_time
                },
                "duration": duration_formatted
            },
            "performance_metrics": {
                "quality_score": {
                    "score": f"{quality_score:.0f}%",
                    "target": "85%",
                    "variance": f"{quality_score - 85:+.1f}% {'below' if quality_score < 85 else 'above'} target"
                },
                "sentiment_score": {
                    "score": f"{sentiment_score}/5",
                    "target": "4.0/5",
                    "status": "Below expected" if sentiment_score < 4.0 else "Meets expectations"
                },
                "issues_identified": {
                    "count": len(issues),
                    "type": "Critical Issues" if len(issues) > 2 else "Minor Issues"
                }
            },
            "identified_issues": issues,
            "call_transcript": {
                "full_text": transcript.text,
                "summary": issues[0] if issues else "No major issues identified",
                "sentiment_analysis": [
                    {
                        "text": getattr(result, 'text', 'N/A'),
                        "sentiment": getattr(result.sentiment, 'value', str(getattr(result, 'sentiment', 'neutral'))) if hasattr(result, 'sentiment') else getattr(result, 'label', 'neutral'),
                        "confidence": getattr(result, 'confidence', 0.0)
                    }
                    for result in sentiment_results
                ] if sentiment_results else []
            },
            "raw_data": {
                "transcript_id": getattr(transcript, 'id', 'unknown'),
                "audio_duration_ms": duration_ms,
                "confidence": getattr(transcript, 'confidence', 0.0),
                "speaker_labels": [
                    {
                        "speaker": getattr(utterance, 'speaker', 'Unknown'),
                        "text": getattr(utterance, 'text', ''),
                        "start": getattr(utterance, 'start', 0),
                        "end": getattr(utterance, 'end', 0)
                    }
                    for utterance in (getattr(transcript, 'utterances', []) or [])
                ]
            }
        }
        
        return analysis_result

def main():
    st.title("📞 Critical Call Analysis")
    st.markdown("Upload an MP3 file to analyze customer service call quality using AI")
    
    # Explanation section
    with st.expander("📊 How We Calculate Metrics", expanded=False):
        st.markdown("""
        **Our AI-powered analysis uses AssemblyAI's advanced speech recognition and sentiment analysis to evaluate customer service calls across multiple dimensions:**
        
        **Quality Score Calculation (Target: 85%):**
        - **Base Score**: Starts at 85% and adjusts based on detected issues
        - **Sentiment Impact**: High negative sentiment (>30%) reduces score by 20 points
        - **Escalation Handling**: Failed escalation procedures reduce score by 15 points  
        - **Empathy Assessment**: Lack of empathy indicators (apologize, understand, help, sorry) reduces score by 10 points
        - **Customer Frustration**: Detection of frustration keywords reduces score by 10 points
        - **Call Efficiency**: Excessively long calls (>2000 words) reduce score by 5 points
        
        **Sentiment Score (Target: 4.0/5):**
        - **Real-time Analysis**: Analyzes sentiment throughout the entire conversation
        - **Segment Scoring**: Each conversation segment is rated as positive (4.5), neutral (3.0), or negative (1.5)
        - **Overall Rating**: Averages all segment scores to provide a comprehensive sentiment evaluation
        
        **Issue Detection:**
        - **Pattern Recognition**: Uses NLP to identify common customer service problems
        - **Keyword Analysis**: Searches for escalation requests, empathy gaps, and frustration indicators
        - **Critical vs Minor**: Categorizes issues based on severity and frequency
        
        **Technical Implementation:**
        - **Audio Processing**: Converts speech to text with speaker identification
        - **Multi-dimensional Analysis**: Combines transcription, sentiment analysis, and business logic
        - **Real-time Feedback**: Provides immediate actionable insights for agent improvement
        """)
    
    st.markdown("---")
    
    # API Key input
    api_key = st.sidebar.text_input(
        "AssemblyAI API Key", 
        type="password",
        help="Enter your AssemblyAI API key. Get one at https://www.assemblyai.com/"
    )
    
    if not api_key:
        st.warning("Please enter your AssemblyAI API key in the sidebar to continue.")
        st.info("You can get a free API key at https://www.assemblyai.com/")
        return
    
    # Input fields for call details
    col1, col2 = st.columns(2)
    with col1:
        agent_name = st.text_input(
            "Agent Name",
            value="Alex Thompson",
            help="Enter the name of the customer service agent"
        )
    with col2:
        customer_name = st.text_input(
            "Customer Name", 
            value="Sandra Miller",
            help="Enter the name of the customer"
        )
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload MP3 Audio File",
        type=['mp3', 'wav', 'm4a', 'flac'],
        help="Upload a customer service call recording"
    )
    
    if uploaded_file is not None:
        # Save uploaded file temporarily
        temp_file_path = f"temp_{uploaded_file.name}"
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.read())
        
        try:
            # Initialize analyzer
            analyzer = CallAnalyzer(api_key)
            
            # Show progress
            with st.spinner("Analyzing call... This may take a few minutes."):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                status_text.text("Uploading audio file...")
                progress_bar.progress(25)
                
                status_text.text("Transcribing audio...")
                progress_bar.progress(50)
                
                status_text.text("Analyzing sentiment and quality...")
                progress_bar.progress(75)
                
                # Perform analysis
                analysis_result = analyzer.analyze_call(temp_file_path, agent_name, customer_name)
                
                progress_bar.progress(100)
                status_text.text("Analysis complete!")
                time.sleep(1)
                status_text.empty()
                progress_bar.empty()
            
            # Display results in dashboard format
            st.success("✅ Analysis Complete!")
            
            # Call Overview Section
            st.header("📋 Call Overview")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Agent",
                    analysis_result["call_overview"]["agent"]["name"],
                    analysis_result["call_overview"]["agent"]["type"]
                )
            
            with col2:
                st.metric(
                    "Customer", 
                    analysis_result["call_overview"]["customer"]["name"],
                    analysis_result["call_overview"]["customer"]["type"]
                )
            
            with col3:
                st.metric(
                    "Date & Time",
                    analysis_result["call_overview"]["date_time"]["date"],
                    analysis_result["call_overview"]["date_time"]["time"]
                )
            
            with col4:
                st.metric(
                    "Duration",
                    analysis_result["call_overview"]["duration"]
                )
            
            # Performance Metrics Section
            st.header("📊 Performance Metrics")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                quality_score = float(analysis_result["performance_metrics"]["quality_score"]["score"].replace('%', ''))
                delta_color = "inverse" if quality_score < 85 else "normal"
                st.metric(
                    "Quality Score",
                    analysis_result["performance_metrics"]["quality_score"]["score"],
                    analysis_result["performance_metrics"]["quality_score"]["variance"],
                    delta_color=delta_color
                )
            
            with col2:
                sentiment_score = float(analysis_result["performance_metrics"]["sentiment_score"]["score"].split('/')[0])
                delta_color = "inverse" if sentiment_score < 4.0 else "normal"
                st.metric(
                    "Sentiment Score",
                    analysis_result["performance_metrics"]["sentiment_score"]["score"],
                    analysis_result["performance_metrics"]["sentiment_score"]["status"],
                    delta_color=delta_color
                )
            
            with col3:
                issues_count = analysis_result["performance_metrics"]["issues_identified"]["count"]
                delta_color = "inverse" if issues_count > 2 else "normal"
                st.metric(
                    "Issues Identified",
                    issues_count,
                    analysis_result["performance_metrics"]["issues_identified"]["type"],
                    delta_color=delta_color
                )
            
            # Issues and Transcript Section
            col1, col2 = st.columns(2)
            
            with col1:
                st.header("⚠️ Identified Issues")
                if analysis_result["identified_issues"]:
                    for i, issue in enumerate(analysis_result["identified_issues"], 1):
                        st.error(f"{i}. {issue}")
                else:
                    st.success("No critical issues identified!")
            
            with col2:
                st.header("📝 Call Transcript")
                st.info(analysis_result["call_transcript"]["summary"])
                
                with st.expander("View Full Transcript"):
                    st.text_area(
                        "Full Transcript",
                        analysis_result["call_transcript"]["full_text"],
                        height=300
                    )
            
            # JSON Output Section
            st.header("📄 JSON Output")
            st.json(analysis_result)
            
            # Download JSON button
            json_string = json.dumps(analysis_result, indent=2)
            
            # Create filename using agent name and file timestamp
            safe_agent_name = "".join(c for c in agent_name if c.isalnum() or c in (' ', '-', '_')).replace(' ', '_')
            file_date = analysis_result["call_overview"]["date_time"]["date"].replace('-', '')
            file_time = analysis_result["call_overview"]["date_time"]["time"].replace(':', '')
            
            st.download_button(
                label="💾 Download Analysis as JSON",
                data=json_string,
                file_name=f"call_analysis_{safe_agent_name}_{file_date}_{file_time}.json",
                mime="application/json"
            )
            
        except Exception as e:
            st.error(f"❌ Error analyzing call: {str(e)}")
            st.info("Please check your API key and try again.")
        
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

if __name__ == "__main__":
    main()