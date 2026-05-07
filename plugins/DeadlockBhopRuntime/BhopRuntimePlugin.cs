using System.Numerics;
using DeadworksManaged.Api;

namespace DeadlockBhopRuntime;

/// <summary>
/// Roam-only runtime shim for imported CS2 bhop maps.
///
/// This deliberately does not implement timers/checkpoints. Its job is only to
/// keep a custom movement map playable under Deadlock rules: assign a hero/team,
/// apply movement-friendly server cvars, and block native environmental/out-of-
/// play damage while the map-side fix is being tested.
/// </summary>
public sealed class BhopRuntimePlugin : DeadworksPluginBase
{
    public override string Name => "DeadlockBhopRuntime";

    private readonly List<Vector3> _spawnCandidates = new();
    private bool _active;
    private int _blockedDamageLogs;

    public override void OnLoad(bool isReload)
    {
        Console.WriteLine($"[{Name}] loaded reload={isReload}");
    }

    public override void OnUnload()
    {
        _spawnCandidates.Clear();
        _active = false;
        _blockedDamageLogs = 0;
    }

    public override void OnStartupServer()
    {
        _spawnCandidates.Clear();
        _blockedDamageLogs = 0;
        _active = IsBhopMap();

        if (!_active)
        {
            Console.WriteLine($"[{Name}] inactive on map '{Server.MapName}'");
            return;
        }

        Console.WriteLine($"[{Name}] active on map '{Server.MapName}'");
        AddKnownMapStarts();

        Exec("sv_cheats 1");
        Exec("citadel_npc_spawn_enabled 0");
        Exec("citadel_allow_purchasing_anywhere 1");
        Exec("citadel_hero_demo_enable_fast_stamina 1");
        Exec("citadel_hero_demo_enable_unlimited_ammo 1");
        Exec("citadel_player_spawn_time_max_respawn_time 1");
        Exec("sv_maxvelocity 99999");
        Exec("sv_airaccelerate 1000");
        Exec("sv_accelerate 255");
        Exec("sv_maxspeed 99999");
        Exec("sv_falldamage_scale 0");
    }

    public override void OnClientFullConnect(ClientFullConnectEvent args)
    {
        if (!_active) return;

        var controller = Players.FromSlot(args.Slot);
        if (controller == null) return;

        controller.ChangeTeam(2);
        controller.SelectHero(Heroes.Viscous);
        controller.HudAnnounce("BHOP", "Roam runtime active: native map damage blocked");

        // Let Deadlock finish creating the hero pawn, then optionally correct to
        // the first discovered start if the stock spawn picked a bad point.
        Timer.Once(2.Seconds(), () => TeleportToStart(controller));
    }

    public override void OnEntitySpawned(EntitySpawnedEvent args)
    {
        if (!_active) return;

        var ent = args.Entity;
        var designer = ent.DesignerName;
        var name = ent.Name;

        if (designer is "info_player_terrorist" or "info_player_counterterrorist" or "info_player_start" or "info_team_spawn" ||
            name.Contains("start", StringComparison.OrdinalIgnoreCase))
        {
            if (ent.Position != Vector3.Zero)
                _spawnCandidates.Add(ent.Position);
        }
    }

    public override HookResult OnTakeDamage(TakeDamageEvent args)
    {
        if (!_active) return HookResult.Continue;

        var pawn = args.Entity.As<CCitadelPlayerPawn>();
        if (pawn == null) return HookResult.Continue;

        args.Info.Damage = 0;
        args.Info.TotalledDamage = 0;
        args.Info.DamageFlags |= TakeDamageFlags.PreventDeath |
                                 TakeDamageFlags.SuppressHealthChanges |
                                 TakeDamageFlags.SuppressEffects |
                                 TakeDamageFlags.SuppressDamageRecord |
                                 TakeDamageFlags.SuppressDeathEvent;

        if (pawn.Health < pawn.GetMaxHealth())
            pawn.Health = pawn.GetMaxHealth();

        if (_blockedDamageLogs < 20)
        {
            _blockedDamageLogs++;
            Console.WriteLine($"[{Name}] blocked pawn damage type={args.Info.DamageType} flags={args.Info.DamageFlags} pos={pawn.Position}");
        }

        return HookResult.Stop;
    }

    [Command("r", "restart", Description = "Teleport back to the first bhop start spawn", SuppressChat = true)]
    public void Restart(CCitadelPlayerController controller)
    {
        if (!_active) return;
        TeleportToStart(controller);
    }

    private void TeleportToStart(CCitadelPlayerController controller)
    {
        var start = _spawnCandidates.FirstOrDefault();
        if (start != Vector3.Zero)
            Teleport(controller, start + new Vector3(0, 0, 16));
    }

    private void AddKnownMapStarts()
    {
        if (Server.MapName.Equals("bhop_emevaelx3", StringComparison.OrdinalIgnoreCase))
            _spawnCandidates.Add(new Vector3(-11904, -6096, 97));
        else if (Server.MapName.Equals("bhop_colour", StringComparison.OrdinalIgnoreCase))
            _spawnCandidates.Add(new Vector3(3720, 4792, 128));
    }

    private static void Teleport(CCitadelPlayerController controller, Vector3 pos)
    {
        var pawn = controller.GetHeroPawn();
        if (pawn == null) return;
        pawn.Health = pawn.GetMaxHealth();
        pawn.Teleport(position: pos, velocity: Vector3.Zero);
    }

    private static bool IsBhopMap()
    {
        var map = Server.MapName ?? "";
        return map.Equals("bhop_emevaelx3", StringComparison.OrdinalIgnoreCase) ||
               map.Contains("bhop", StringComparison.OrdinalIgnoreCase) ||
               map.Contains("movement", StringComparison.OrdinalIgnoreCase);
    }

    private static void Exec(string command)
    {
        try { Server.ExecuteCommand(command); }
        catch (Exception ex) { Console.WriteLine($"[DeadlockBhopRuntime] command failed '{command}': {ex.Message}"); }
    }
}
