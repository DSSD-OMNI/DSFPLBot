import numpy as np
from apps.dsfplbot.fpl_data_reader import get_manager_history

WEIGHTS = {
    'xG': 0.13,
    'xA': 0.08,
    'form_last_5': 0.07,
    'minutes_last_5': 0.07,
    'ict_index': 0.05,
    'bonus_points_avg': 0.05,
    'selected_by_percent': 0.04,
    'opponent_elo': 0.08,
    'home_advantage': 0.05,
    'fixture_difficulty': 0.04,
    'team_xG_trend': 0.05,
    'opponent_xG_conceded': 0.04,
    'days_since_last_match': 0.03,
    'international_break_flag': 0.02,
    'transfers_in_round': 0.04,
    'volatility': 0.03,
    'form_trend': 0.04,
    'captain_diversity': 0.03,
    'chips_used': 0.04,
    'cbit': 0.02,
    'non_penalty_xG': 0.03,
}

async def calculate_lri_for_manager(entry_id: int, league_id: int) -> float:
    """Заглушка для LRI. Позже будет реальный расчёт."""
    # TODO: реализовать полноценный расчёт на основе данных из БД
    return 5.0

def generate_personalized_advice(standings, weeks):
    """Генерирует советы на основе данных таблицы."""
    if not standings:
        return "Нет данных для анализа."
    
    advice_lines = []
    # Средние по лиге
    form_values = [s.get('form', 0) for s in standings if s.get('form')]
    chips_values = [s.get('chips_used', 0) for s in standings if s.get('chips_used')]
    avg_form = np.mean(form_values) if form_values else 0
    avg_chips = np.mean(chips_values) if chips_values else 0

    for s in standings:
        name = s.get('manager_name', 'Unknown')
        adv = []
        if s.get('form', 0) < avg_form - 2:
            adv.append("📉 Ваш темп ниже среднего. Присмотритесь к игрокам в хорошей форме.")
        elif s.get('form', 0) > avg_form + 2:
            adv.append("📈 Вы в отличной форме! Продолжайте в том же духе.")
        if s.get('chips_used', 0) < avg_chips - 1:
            adv.append("🎯 Вы использовали меньше чипов, чем соперники. Возможно, пора активировать один из них.")
        elif s.get('chips_used', 0) >= 3:
            adv.append("🃏 Вы активно используете чипы — это даёт преимущество.")
        if s.get('last_transfers'):
            adv.append("🔄 Вы сделали трансферы в прошлом туре — отличная активность.")
        else:
            adv.append("🔄 Вы не делали трансферов в прошлом туре. Может, стоит усилить состав?")
        if s.get('games_played', weeks) < weeks:
            adv.append(f"⚠️ У вас мало данных за выбранный период ({s['games_played']} тур(ов)). Результат может быть неточным.")
        if adv:
            advice_lines.append(f"• *{name}*: " + " ".join(adv))
    return "\n".join(advice_lines) if advice_lines else "✨ У всех менеджеров отличные показатели!"
