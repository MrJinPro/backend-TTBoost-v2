import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class EventsFilterBar extends StatelessWidget {
  final String active;
  final void Function(String) onChange;
  const EventsFilterBar({super.key, required this.active, required this.onChange});
  static const filters = ['all','gift','chat','follow','battle'];
  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      children: filters.map((f){
        final selected = active==f;
        final label = switch(f){
          'all' => 'All',
          'gift' => 'Подарки',
          'chat' => 'Сообщения',
          'follow' => 'Подписки',
          'battle' => 'Battle',
          _ => f,
        };
        return ChoiceChip(
          label: Text(label),
          selected: selected,
          onSelected: (_)=>onChange(f),
          selectedColor: AppColors.accentCyan.withOpacity(0.25),
          backgroundColor: AppColors.cardBackground,
          labelStyle: TextStyle(color: selected?AppColors.accentCyan:AppColors.secondaryText),
          shape: RoundedRectangleBorder(
            side: BorderSide(color: selected?AppColors.accentCyan:AppColors.cardBorder),
            borderRadius: BorderRadius.circular(14),
          ),
        );
      }).toList(),
    );
  }
}
