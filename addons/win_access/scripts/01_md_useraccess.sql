/*
  Repairs Shaka_DW.MD.UserAccess / vwUserAccess so Odoo can own the per-user BI row access.
  Run ONCE, by hand, as a DBA against database Shaka_DW. Safe to re-run.

  Why:
    - Shaka_DW.MD.vwUserAccess currently reads [ShakasystemDB].MD.vwUserAccess, a database that does not exist.
    - The DAX RLS filter needs UserName, EntityID (Odoo/system-DB ids, e.g. DimWarehouse = 1000171),
      EntityColumnName, MemberID, IsAllMember, IsAllReader.
    - The 532 legacy rows use the OLD Shaka_DW.MD.Entity id space (DimWarehouse = 171), so they would never
      match the DAX. They are copied to MD.UserAccess_legacy and removed from the live table.

  Everything that touches the new columns goes through EXEC() so the batch compiles before they exist.
*/
SET XACT_ABORT ON;
BEGIN TRAN;

-- 1. new columns (Odoo writes the user name and entity name directly, no SCR.User GUID needed)
IF COL_LENGTH('MD.UserAccess', 'UserName')         IS NULL ALTER TABLE MD.UserAccess ADD UserName         varchar(100) NULL;
IF COL_LENGTH('MD.UserAccess', 'EntityName')       IS NULL ALTER TABLE MD.UserAccess ADD EntityName       varchar(50)  NULL;
IF COL_LENGTH('MD.UserAccess', 'EntityColumnName') IS NULL ALTER TABLE MD.UserAccess ADD EntityColumnName varchar(50)  NULL;

-- 2. quarantine legacy rows (no UserName = written by the old process, old entity ids)
IF OBJECT_ID('MD.UserAccess_legacy') IS NULL
    EXEC('SELECT * INTO MD.UserAccess_legacy FROM MD.UserAccess WHERE UserName IS NULL');
EXEC('DELETE FROM MD.UserAccess WHERE UserName IS NULL');

-- 3. local view with the exact nine columns the DAX and Power BI expect
EXEC('CREATE OR ALTER VIEW MD.vwUserAccess AS
SELECT ID,
       CAST(NULL AS int)               AS UserID,
       UserName,
       CAST(EntityID AS bigint)        AS EntityId,
       CAST(EntityName AS varchar(50)) AS Name,
       MemberID,
       IsAllMember,
       IsAllReader,
       EntityColumnName
FROM MD.UserAccess');

-- 4. import the live grants from the ERP system database, skipping any already present
IF DB_ID('Shaka_System_DB') IS NOT NULL
    EXEC('INSERT INTO MD.UserAccess (UserName, EntityID, EntityName, MemberID, IsAllReader, IsAllMember, EntityColumnName)
          SELECT s.UserName, s.EntityId, s.Name, s.MemberID, s.IsAllReader, s.IsAllMember, s.EntityColumnName
          FROM Shaka_System_DB.MD.vwUserAccess s
          WHERE NOT EXISTS (SELECT 1 FROM MD.UserAccess a
                            WHERE a.UserName = s.UserName AND a.EntityID = s.EntityId
                              AND ISNULL(a.MemberID, -1) = ISNULL(s.MemberID, -1)
                              AND ISNULL(a.EntityColumnName, '''') = ISNULL(s.EntityColumnName, ''''))');

COMMIT TRAN;

-- 5. check: must return rows, not an error
SELECT * FROM MD.vwUserAccess;
