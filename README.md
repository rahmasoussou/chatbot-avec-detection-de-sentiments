# ✨ Premium Chatbot Intelligence — Projet démo pour CV

## 🌟 Fonctionnalités Premium

### 🤖 Backend (Flask)
- **Intégration Groq API** (LLaMA 70B) pour des réponses ultra-rapides
- **Analyse de sentiment en temps réel** (TextBlob) sur chaque message utilisateur
- **Base de données SQLite** avec historique complet et métadonnées
- **Sessions utilisateur** avec suivi des conversations
- **Dashboard admin** avec graphiques et analytics

### 🎨 Frontend (Moderne & Luxueux)
- **UI/UX premium** : gradients, animations fluides, glassmorphism
- **Synthèse vocale (Text-to-Speech)** : lecture automatique des réponses
- **Reconnaissance vocale** : dictée des messages (Web Speech API)
- **Indicateur de sentiment** : badges colorés sur chaque message
- **Design responsive** : s'adapte à tous les appareils

### 📊 Analytics & Monitoring
- Statistiques en temps réel (messages, sessions)
- Analyse des sentiments par conversation
- Graphiques d'activité quotidienne
- Historique détaillé des conversations

## 🚀 Installation (5 minutes)

```bash
# 1. Cloner ou créer le projet
mkdir premium-chatbot && cd premium-chatbot

# 2. Créer environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer la clé API
cp .env.example .env
# Éditer .env avec votre clé Groq

# 5. Lancer l'application
python app.py