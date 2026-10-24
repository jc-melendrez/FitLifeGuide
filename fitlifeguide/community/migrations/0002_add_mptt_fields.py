from django.db import migrations, models
import mptt.fields
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('community', '0001_initial'),
        ('community', '0003_blogpost_likes_forumpost_likes_thread_likes_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='forumcomment',
            name='level',
            field=models.PositiveIntegerField(default=0, editable=False),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='forumcomment',
            name='lft',
            field=models.PositiveIntegerField(default=0, editable=False),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='forumcomment',
            name='rght',
            field=models.PositiveIntegerField(default=0, editable=False),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='forumcomment',
            name='tree_id',
            field=models.PositiveIntegerField(default=0, db_index=True, editable=False),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='forumcomment',
            name='parent',
            field=mptt.fields.TreeForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='community.forumcomment'),
        ),
    ] 