%global with_perftools 0
%global with_redistrib 1
%global with_pandoc    1
%global with_tests     1

# Commit IDs for the (unversioned) redis-doc repository
# https://fedoraproject.org/wiki/Packaging:SourceURL "Commit Revision"
%global doc_commit dc402c61da3c015e49eb6fd00e4a0564d122d645
%global short_doc_commit %(c=%{doc_commit}; echo ${c:0:7})

Name:              redis40u
Version:           4.0.7
Release:           1.ius%{?dist}
Summary:           A persistent key-value database
License:           BSD
URL:               http://redis.io
Source0:           http://download.redis.io/releases/redis-%{version}.tar.gz
Source1:           redis.logrotate
Source2:           redis-sentinel.service
Source3:           redis.service
Source6:           redis-shutdown
Source7:           redis-limit-systemd
Source9:           macros.redis
Source10:          https://github.com/antirez/redis-doc/archive/%{doc_commit}/redis-doc-%{short_doc_commit}.tar.gz

# To refresh patches:
# tar xf redis-xxx.tar.gz && cd redis-xxx && git init && git add . && git commit -m "%%{version} baseline"
# git am %%{patches}
# Then refresh your patches
# git format-patch HEAD~<number of expected patches>
# Update configuration for Fedora
# https://github.com/antirez/redis/pull/3491 - man pages
Patch0001:         0001-1st-man-pageis-for-redis-cli-redis-benchmark-redis-c.patch
# https://github.com/antirez/redis/pull/3494 - symlink
Patch0002:         0002-install-redis-check-rdb-as-a-symlink-instead-of-dupl.patch
%if 0%{?with_perftools}
BuildRequires:     gperftools-devel
%else
BuildRequires:     jemalloc-devel
%endif
%if 0%{?with_tests}
BuildRequires:     procps-ng
BuildRequires:     tcl
%endif
%if 0%{?with_pandoc}
BuildRequires:     pandoc
%endif
BuildRequires:     systemd
# Required for redis-shutdown
Requires:          /bin/awk
Requires:          logrotate
Requires(pre):     shadow-utils
%{?systemd_requires}
Provides:          bundled(hiredis)
Provides:          bundled(lua-libs)
Provides:          bundled(linenoise)
Provides:          redis = %{version}-%{release}
Provides:          redis%{?_isa} = %{version}-%{release}
Conflicts:         redis < %{version}

%global redis_modules_abi 1
%global redis_modules_dir %{_libdir}/redis/modules
Provides:          redis(modules_abi)%{?_isa} = %{redis_modules_abi}

%description
Redis is an advanced key-value store. It is often referred to as a data 
structure server since keys can contain strings, hashes, lists, sets and 
sorted sets.

You can run atomic operations on these types, like appending to a string;
incrementing the value in a hash; pushing to a list; computing set 
intersection, union and difference; or getting the member with highest 
ranking in a sorted set.

In order to achieve its outstanding performance, Redis works with an 
in-memory dataset. Depending on your use case, you can persist it either 
by dumping the dataset to disk every once in a while, or by appending 
each command to a log.

Redis also supports trivial-to-setup master-slave replication, with very 
fast non-blocking first synchronization, auto-reconnection on net split 
and so forth.

Other features include Transactions, Pub/Sub, Lua scripting, Keys with a 
limited time-to-live, and configuration settings to make Redis behave like 
a cache.

You can use Redis from most programming languages also.

%package           devel
Summary:           Development header for Redis module development
# Header-Only Library (https://fedoraproject.org/wiki/Packaging:Guidelines)
Provides:          redis-static = %{version}-%{release}

%description       devel
Header file required for building loadable Redis modules. Detailed
API documentation is available in the redis-doc package.

%package           doc
Summary:           Documentation for Redis including man pages
License:           CC-BY-SA
BuildArch:         noarch

%description       doc
Manual pages and detailed documentation for many aspects of Redis use,
administration and development.

%if 0%{?with_redistrib}
%package           trib
Summary:           Cluster management script for Redis
BuildArch:         noarch
Requires:          ruby
Requires:          rubygem-redis

%description       trib
Redis cluster management utility providing cluster creation, node addition
and removal, status checks, resharding, rebalancing, and other operations.
%endif

%prep
%autosetup -n redis-%{version} -a 10 -p 1
rm -frv deps/jemalloc

# Use system jemalloc library
sed -i -e '/cd jemalloc && /d' deps/Makefile
sed -i -e 's|../deps/jemalloc/lib/libjemalloc.a|-ljemalloc -ldl|g' src/Makefile
sed -i -e 's|-I../deps/jemalloc.*|-DJEMALLOC_NO_DEMANGLE -I/usr/include/jemalloc|g' src/Makefile

# Configuration file changes and additions
sed -i -e 's|^logfile .*$|logfile /var/log/redis/redis.log|g' redis.conf
sed -i -e '$ alogfile /var/log/redis/sentinel.log' sentinel.conf
sed -i -e 's|^dir .*$|dir /var/lib/redis|g' redis.conf

# https://github.com/antirez/redis/issues/2023#issuecomment-56451410
sed -i -e 's|after 1000|after 5000|' tests/integration/replication-2.tcl

# Module API version safety check
api=`sed -n -e 's/#define REDISMODULE_APIVER_[0-9][0-9]* //p' src/redismodule.h`
if test "$api" != "%{redis_modules_abi}"; then
   : Error: Upstream API version is now ${api}, expecting %%{redis_modules_abi}.
   : Update the redis_modules_abi macro, the rpmmacros file, and rebuild.
   exit 1
fi

%if 0%{?with_pandoc}
for doc in $(find redis-doc-%{doc_commit} -name \*.md); do
    pandoc --standalone --from markdown --to html --output ${doc/%md/html} $doc
done
%endif

%if 0%{?with_perftools}
%global malloc_flags	MALLOC=tcmalloc
%else
%global malloc_flags	MALLOC=jemalloc
%endif
%global make_flags	DEBUG="" V="echo" LDFLAGS="%{?__global_ldflags}" CFLAGS+="%{optflags} -fPIC" %{malloc_flags} INSTALL="install -p" PREFIX=%{buildroot}%{_prefix}

%build
make %{?_smp_mflags} %{make_flags} all

%install
make %{make_flags} install

# Filesystem.
install -d %{buildroot}%{_sharedstatedir}/redis
install -d %{buildroot}%{_localstatedir}/log/redis
install -d %{buildroot}%{_localstatedir}/run/redis
install -d %{buildroot}%{redis_modules_dir}

# Install logrotate file.
install -pDm644 %{S:1} %{buildroot}%{_sysconfdir}/logrotate.d/redis

# Install configuration files.
install -pDm640 redis.conf %{buildroot}%{_sysconfdir}/redis.conf
install -pDm640 sentinel.conf %{buildroot}%{_sysconfdir}/redis-sentinel.conf

# Install systemd unit files.
mkdir -p %{buildroot}%{_unitdir}
install -pm644 %{S:3} %{buildroot}%{_unitdir}
install -pm644 %{S:2} %{buildroot}%{_unitdir}

# Install systemd limit files (requires systemd >= 204)
install -p -D -m 644 %{S:7} %{buildroot}%{_sysconfdir}/systemd/system/redis.service.d/limit.conf
install -p -D -m 644 %{S:7} %{buildroot}%{_sysconfdir}/systemd/system/redis-sentinel.service.d/limit.conf

# Fix non-standard-executable-perm error.
chmod 755 %{buildroot}%{_bindir}/redis-*

# Install redis-shutdown
install -pDm755 %{S:6} %{buildroot}%{_libexecdir}/redis-shutdown

# Install redis module header
install -pDm644 src/redismodule.h %{buildroot}%{_includedir}/redismodule.h

%if 0%{?with_redistrib}
# Install redis-trib
install -pDm755 src/redis-trib.rb %{buildroot}%{_bindir}/redis-trib
%endif

# Install man pages
man=$(dirname %{buildroot}%{_mandir})
for page in man/man?/*; do
    install -Dpm644 $page $man/$page
done
ln -s redis-server.1 %{buildroot}%{_mandir}/man1/redis-sentinel.1
ln -s redis.conf.5   %{buildroot}%{_mandir}/man5/redis-sentinel.conf.5

# Install markdown and html pages
pushd redis-doc-%{doc_commit}
find -name \*.md -exec install -Dpm644 {} %{buildroot}%{_pkgdocdir}/{} \;
%if 0%{?with_pandoc}
find -name \*.html -exec install -Dpm644 {} %{buildroot}%{_pkgdocdir}/{} \;
%endif
popd

# Install rpm macros for redis modules
install -pDm644 %{S:9} %{buildroot}%{rpmmacrodir}/macros.redis

%check
%if 0%{?with_tests}
# https://github.com/antirez/redis/issues/1417 (for "taskset -c 1")
taskset -c 1 make %{make_flags} test
make %{make_flags} test-sentinel
%endif

%pre
getent group redis &> /dev/null || \
groupadd -r redis &> /dev/null
getent passwd redis &> /dev/null || \
useradd -r -g redis -d %{_sharedstatedir}/redis -s /sbin/nologin \
-c 'Redis Database Server' redis &> /dev/null
exit 0

%post
%systemd_post redis.service
%systemd_post redis-sentinel.service

%preun
%systemd_preun redis.service
%systemd_preun redis-sentinel.service

%postun
%systemd_postun_with_restart redis.service
%systemd_postun_with_restart redis-sentinel.service

%files
%license COPYING
%exclude %{_pkgdocdir}/*
%doc 00-RELEASENOTES BUGS CONTRIBUTING MANIFESTO README.md
%config(noreplace) %{_sysconfdir}/logrotate.d/redis
%attr(0640, redis, root) %config(noreplace) %{_sysconfdir}/redis.conf
%attr(0640, redis, root) %config(noreplace) %{_sysconfdir}/redis-sentinel.conf
%dir %attr(0750, redis, redis) %{_libdir}/redis
%dir %attr(0750, redis, redis) %{redis_modules_dir}
%dir %attr(0750, redis, redis) %{_sharedstatedir}/redis
%dir %attr(0750, redis, redis) %{_localstatedir}/log/redis
%dir %attr(0750, redis, redis) %ghost %{_localstatedir}/run/redis
%if 0%{?with_redistrib}
%exclude %{_bindir}/redis-trib
%endif
%{_bindir}/redis-*
%{_libexecdir}/redis-*
%{_mandir}/man1/redis*
%{_mandir}/man5/redis*
%{_unitdir}/redis.service
%{_unitdir}/redis-sentinel.service
%dir %{_sysconfdir}/systemd/system/redis.service.d
%config(noreplace) %{_sysconfdir}/systemd/system/redis.service.d/limit.conf
%dir %{_sysconfdir}/systemd/system/redis-sentinel.service.d
%config(noreplace) %{_sysconfdir}/systemd/system/redis-sentinel.service.d/limit.conf

%files devel
%license COPYING
%{_includedir}/redismodule.h
%{rpmmacrodir}/macros.redis

%files doc
%{_pkgdocdir}

%if 0%{?with_redistrib}
%files trib
%license COPYING
%{_bindir}/redis-trib
%endif


%changelog
* Wed Jan 24 2018 Carl George <carl@george.computer> - 4.0.7-1.ius
- Latest upstream

* Mon Dec 11 2017 Carl George <carl@george.computer> - 4.0.6-1.ius
- Latest upstream

* Mon Nov 20 2017 Carl George <carl@george.computer> - 4.0.2-1.ius
- Port from Fedora to IUS
- Move man pages to main package
- Documentation cleanup
- Enable test suite

* Fri Nov 17 2017 Nathan Scott <nathans@redhat.com> - 4.0.2-2
- Install the base modules directories, owned by the main package.

* Tue Oct 31 2017 Nathan Scott <nathans@redhat.com> - 4.0.2-1
- Upstream 4.0.2 release.  (RHBZ #1389592)
- Add redis-devel for loadable module development.
- Add redis-doc for man pages and detailed documentation.
- Provide redis-check-aof as a symlink to redis-server also now.

* Tue Sep 26 2017 Nathan Scott <nathans@redhat.com> - 3.2.11-1
- Upstream 3.2.11 bug-fix-only release
- Switch to using Type=notify for Redis systemd services (RHBZ #1172841)
- Add Provides:bundled hiredis, linenoise, lua-libs clauses (RHBZ #788500)

* Mon Aug 14 2017 Nathan Scott <nathans@redhat.com> - 3.2.10-2
- Add redis-trib based on patch from Sebastian Saletnik.  (RHBZ #1215654)

* Thu Aug 03 2017 Fedora Release Engineering <releng@fedoraproject.org> - 3.2.9-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Mon Jul 31 2017 Nathan Scott <nathans@redhat.com> - 3.2.10-1
- Upstream 3.2.10 release
- Ensure both the redis and redis-sentinel service files set correct perms
- Dropped systemd tmpfiles source, handled directly in systemd service files

* Thu Jul 27 2017 Fedora Release Engineering <releng@fedoraproject.org> - 3.2.9-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Mon May 29 2017 Nathan Scott <nathans@redhat.com> - 3.2.9-1
- Upstream 3.2.9
- Add RuntimeDirectory=redis to systemd unit file (RHBZ #1454700)
- Mark rundir as %ghost since it may disappear (tmpfs - #1454700)
- Fix a shutdown failure with Unix domain sockets (RHBZ #1444988)

* Mon Feb 20 2017 Haïkel Guémar <hguemar@fedoraproject.org> - 3.2.8-1
- Upstream 3.2.8
- bugfix for #3796 (MIGRATE could cause server crash  after socket error)

* Sat Feb 11 2017 Fedora Release Engineering <releng@fedoraproject.org> - 3.2.7-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Sat Feb  4 2017 Haïkel Guémar <hguemar@fedoraproject.org> - 3.2.7-1
- Upstream 3.2.7 (important security fix)

* Sat Nov 05 2016 Alan Pevec <apevec AT redhat.com> - 3.2.4-2
- Install tmpfiles and /run/redis for legacy configurations

* Mon Sep 26 2016 Haïkel Guémar <hguemar@fedoraproject.org> - 3.2.4-1
- Upstream 3.2.4
- Fix buffer overlow (TALOS-2016-0206)

* Wed Sep 14 2016 Remi Collet <remi@fedoraproject.org> - 3.2.3-2
- add missing man pages #1374577
  using patch from https://github.com/antirez/redis/pull/3491
- data and configuration should not be publicly readable #1374700
- remove /var/run/redis with systemd #1374728
- provide redis-check-rdb as a symlink to redis-server #1374736
  using patch from https://github.com/antirez/redis/pull/3494
- move redis-shutdown to libexec

* Thu Aug  4 2016 Haïkel Guémar <hguemar@fedoraproject.org> - 3.2.3-1
- Upstream 3.2.3
- Security fix for CVE-2013-7458 (redis-cli history world readable)
- RHBZ#1363670 RHBZ#1363671

* Mon Feb  8 2016 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.6-3
- Fix redis-shutdown to handle password-protected instances shutdown

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 3.0.6-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Sat Dec 19 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.6-1
- Upstream 3.0.6 (RHBZ#1272281)

* Fri Oct 16 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.5-1
- Upstream 3.0.5
- Fix slave/master replication hanging forever in certain case

* Mon Sep 07 2015 Christopher Meng <rpm@cicku.me> - 3.0.4-1
- Update to 3.0.4

* Sun Aug 30 2015 Christopher Meng <rpm@cicku.me> - 3.0.3-2
- Rebuilt for jemalloc 4.0.0

* Tue Jul 21 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.3-1
- Upstream 3.0.3

* Thu Jun 18 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 3.0.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Thu Jun 04 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.2-1
- Upstream 3.0.2 (RHBZ #1228245)
- Fix Lua sandbox escape and arbitrary code execution (RHBZ #1228331)

* Sat May 09 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.1-1
- Upstream 3.0.1 (RHBZ #1208322)

* Tue Apr 14 2015 Remi Collet <remi@fedoraproject.org> - 3.0.0-2
- rotate /var/log/redis/sentinel.log

* Thu Apr  2 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.0-1
- Upstream 3.0.0 (RHBZ #1208322)

* Thu Mar 26 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.19-2
- Fix redis-shutdown on multiple NIC setup (RHBZ #1201237)

* Fri Feb 27 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.19-1
- Upstream 2.8.19 (RHBZ #1175232)
- Fix permissions for tmpfiles (RHBZ #1182913)
- Add limits config files
- Spec cleanups

* Fri Dec 05 2014 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.18-1
- Upstream 2.8.18
- Rebased patches

* Sat Sep 20 2014 Remi Collet <remi@fedoraproject.org> - 2.8.17-1
- Upstream 2.8.17
- fix redis-sentinel service unit file for systemd
- fix redis-shutdown for sentinel
- also use redis-shutdown in init scripts

* Wed Sep 17 2014 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.15-2
- Minor fix to redis-shutdown (from Remi Collet)

* Sat Sep 13 2014 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.15-1
- Upstream 2.8.15 (critical bugfix for sentinel)
- Fix to sentinel systemd service and configuration (thanks Remi)
- Refresh patch management

* Thu Sep 11 2014 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.14-2
- Cleanup spec
- Fix shutdown for redis-{server,sentinel}
- Backport fixes from Remi Collet repository (ie: sentinel working)

* Thu Sep 11 2014 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.14-1
- Upstream 2.8.14 (RHBZ #1136287)
- Bugfix for lua scripting users (server crash)
- Refresh patches
- backport spec from EPEL7 (thanks Warren)

* Wed Jul 16 2014 Christopher Meng <rpm@cicku.me> - 2.8.13-1
- Update to 2.8.13

* Tue Jun 24 2014 Christopher Meng <rpm@cicku.me> - 2.8.12-1
- Update to 2.8.12

* Wed Jun 18 2014 Christopher Meng <rpm@cicku.me> - 2.8.11-1
- Update to 2.8.11

* Sun Jun 08 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.6.16-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Fri Sep 06 2013 Fabian Deutsch <fabian.deutsch@gmx.de> - 2.6.16-1
- Update to 2.6.16
- Fix rhbz#973151
- Fix rhbz#656683
- Fix rhbz#977357 (Jan Vcelak <jvcelak@fedoraproject.org>)

* Sun Aug 04 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.6.13-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Tue Jul 23 2013 Peter Robinson <pbrobinson@fedoraproject.org> 2.6.13-4
- ARM has gperftools

* Wed Jun 19 2013 Fabian Deutsch <fabiand@fedoraproject.org> - 2.6.13-3
- Modify jemalloc patch for s390 compatibility (Thanks sharkcz)

* Fri Jun 07 2013 Fabian Deutsch <fabiand@fedoraproject.org> - 2.6.13-2
- Unbundle jemalloc

* Fri Jun 07 2013 Fabian Deutsch <fabiand@fedoraproject.org> - 2.6.13-1
- Add compile PIE flag (rhbz#955459)
- Update to redis 2.6.13 (rhbz#820919)

* Thu Feb 14 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.6.7-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Thu Dec 27 2012 Silas Sewell <silas@sewell.org> - 2.6.7-1
- Update to redis 2.6.7

* Sat Jul 21 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.4.15-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Sun Jul 08 2012 Silas Sewell <silas@sewell.org> - 2.4.15-2
- Remove TODO from docs

* Sun Jul 08 2012 Silas Sewell <silas@sewell.org> - 2.4.15-1
- Update to redis 2.4.15

* Sat May 19 2012 Silas Sewell <silas@sewell.org> - 2.4.13-1
- Update to redis 2.4.13

* Sat Mar 31 2012 Silas Sewell <silas@sewell.org> - 2.4.10-1
- Update to redis 2.4.10

* Fri Feb 24 2012 Silas Sewell <silas@sewell.org> - 2.4.8-1
- Update to redis 2.4.8

* Sat Feb 04 2012 Silas Sewell <silas@sewell.org> - 2.4.7-1
- Update to redis 2.4.7

* Wed Feb 01 2012 Fabian Deutsch <fabiand@fedoraproject.org> - 2.4.6-4
- Fixed a typo in the spec

* Tue Jan 31 2012 Fabian Deutsch <fabiand@fedoraproject.org> - 2.4.6-3
- Fix .service file, to match config (Type=simple).

* Tue Jan 31 2012 Fabian Deutsch <fabiand@fedoraproject.org> - 2.4.6-2
- Fix .service file, credits go to Timon.

* Thu Jan 12 2012 Fabian Deutsch <fabiand@fedoraproject.org> - 2.4.6-1
- Update to 2.4.6
- systemd unit file added
- Compiler flags changed to compile 2.4.6
- Remove doc/ and Changelog

* Sun Jul 24 2011 Silas Sewell <silas@sewell.org> - 2.2.12-1
- Update to redis 2.2.12

* Fri May 06 2011 Dan Horák <dan[at]danny.cz> - 2.2.5-2
- google-perftools exists only on selected architectures

* Sat Apr 23 2011 Silas Sewell <silas@sewell.ch> - 2.2.5-1
- Update to redis 2.2.5

* Sat Mar 26 2011 Silas Sewell <silas@sewell.ch> - 2.2.2-1
- Update to redis 2.2.2

* Wed Feb 09 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.0.4-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Sun Dec 19 2010 Silas Sewell <silas@sewell.ch> - 2.0.4-1
- Update to redis 2.0.4

* Tue Oct 19 2010 Silas Sewell <silas@sewell.ch> - 2.0.3-1
- Update to redis 2.0.3

* Fri Oct 08 2010 Silas Sewell <silas@sewell.ch> - 2.0.2-1
- Update to redis 2.0.2
- Disable checks section for el5

* Sat Sep 11 2010 Silas Sewell <silas@sewell.ch> - 2.0.1-1
- Update to redis 2.0.1

* Sat Sep 04 2010 Silas Sewell <silas@sewell.ch> - 2.0.0-1
- Update to redis 2.0.0

* Thu Sep 02 2010 Silas Sewell <silas@sewell.ch> - 1.2.6-3
- Add Fedora build flags
- Send all scriplet output to /dev/null
- Remove debugging flags
- Add redis.conf check to init script

* Mon Aug 16 2010 Silas Sewell <silas@sewell.ch> - 1.2.6-2
- Don't compress man pages
- Use patch to fix redis.conf

* Tue Jul 06 2010 Silas Sewell <silas@sewell.ch> - 1.2.6-1
- Initial package
