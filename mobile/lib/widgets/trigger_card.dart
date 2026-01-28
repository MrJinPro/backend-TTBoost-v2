import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class TriggerCard extends StatelessWidget {
  final String title;
  final String subtitle;
  final IconData icon;
  final bool enabled;
  final int executions;
  final VoidCallback onToggle;
  final VoidCallback? onDelete;
  final VoidCallback? onEdit;
  const TriggerCard({super.key, required this.title, required this.subtitle, required this.icon, required this.enabled, required this.executions, required this.onToggle, this.onDelete, this.onEdit});
  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 8),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.cardBorder),
      ),
      child: Row(
        children: [
          Container(
            width: 46,
            height: 46,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(14),
              gradient: const LinearGradient(colors: [Color(0xFF00E5FF), Color(0xFF8A2BE2)]),
            ),
            child: Icon(icon, color: Colors.white),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                const SizedBox(height:4),
                Text('Выполнен $executions раз', style: const TextStyle(color: AppColors.secondaryText, fontSize: 12)),
                Text(subtitle, style: const TextStyle(color: AppColors.secondaryText, fontSize: 11)),
              ],
            ),
          ),
          Column(
            children: [
              if (onEdit != null)
                IconButton(
                  icon: const Icon(Icons.edit),
                  tooltip: 'Редактировать',
                  onPressed: onEdit,
                ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: enabled? AppColors.accentGreen.withOpacity(0.15):AppColors.accentPurple.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Text(enabled? 'ON':'OFF', style: TextStyle(color: enabled?AppColors.accentGreen:AppColors.accentPurple, fontSize: 12, fontWeight: FontWeight.bold)),
              ),
              Switch(
                value: enabled,
                activeColor: AppColors.accentGreen,
                onChanged: (_)=>onToggle(),
              ),
              if (onDelete!=null)
                IconButton(icon: const Icon(Icons.delete, size:20, color: AppColors.accentRed), onPressed: onDelete, tooltip:'Удалить'),
            ],
          )
        ],
      ),
    );
  }
}
